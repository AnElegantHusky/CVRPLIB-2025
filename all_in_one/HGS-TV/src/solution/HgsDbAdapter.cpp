#include "HgsDbAdapter.h"

#include "../Individual.h"

#include <algorithm>
#include <cctype>
#include <iostream>
#include <sstream>

#include "sqlite3.h"

namespace genvrp {

    // Serialise routes as a JSON-like string: [[1,2],[3,4],...]
    static std::string routesToJsonString(const std::vector<std::vector<int>>& routes) {
        std::stringstream ss;
        ss << "[";
        bool firstRoute = true;

        for(const auto& route : routes) {
            if(route.empty()) {
                continue;
            }

            if(!firstRoute) {
                ss << ", ";
            }
            firstRoute = false;

            ss << "[";
            bool firstCust = true;
            for(int c : route) {
                if(!firstCust) {
                    ss << ", ";
                }
                firstCust = false;
                ss << c;
            }
            ss << "]";
        }

        ss << "]";
        return ss.str();
    }

    // Lightweight parser turning a string like [[1,2],[3,4]] into vector<vector<int>>
    static std::vector<std::vector<int>> parseJsonRoutes(const std::string& json) {
        std::vector<std::vector<int>> routes;
        std::vector<int> currentRoute;
        std::string numBuf;
        bool insideRoute = false;

        for(char c : json) {
            if(c == '[') {
                insideRoute = true;
                currentRoute.clear();
            } else if(c == ']') {
                if(!numBuf.empty()) {
                    currentRoute.push_back(std::stoi(numBuf));
                    numBuf.clear();
                }
                if(insideRoute && !currentRoute.empty()) {
                    routes.push_back(currentRoute);
                    currentRoute.clear();
                }
                insideRoute = false;
            } else if(c == ',') {
                if(insideRoute && !numBuf.empty()) {
                    currentRoute.push_back(std::stoi(numBuf));
                    numBuf.clear();
                }
            } else if(std::isdigit(static_cast<unsigned char>(c)) || c == '-') {
                numBuf += c;
            }
        }

        return routes;
    }

    bool loadBestRoutesFromDb(const HgsDbConfig& cfg, std::vector<std::vector<int>>& routes, double& score) {
        routes.clear();
        score = 0.0;

        if(cfg.dbPath.empty()) {
            return false;
        }

        sqlite3* db = nullptr;
        if(sqlite3_open_v2(cfg.dbPath.c_str(), &db, SQLITE_OPEN_READONLY, nullptr) != SQLITE_OK) {
            if(db) {
                sqlite3_close(db);
            }
            return false;
        }

        sqlite3_busy_timeout(db, 30000);

        const char* sql = "SELECT solution, score FROM global_best WHERE id = 1";
        sqlite3_stmt* stmt = nullptr;

        std::string rawJson;
        bool found = false;

        if(sqlite3_prepare_v2(db, sql, -1, &stmt, nullptr) == SQLITE_OK) {
            if(sqlite3_step(stmt) == SQLITE_ROW) {
                const auto* text = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 0));
                score = sqlite3_column_double(stmt, 1);

                if(text && score < 1e19) {
                    rawJson = text;
                    found = true;
                }
            }
        }

        if(stmt) {
            sqlite3_finalize(stmt);
        }
        sqlite3_close(db);

        if(!found || rawJson.empty()) {
            return false;
        }

        routes = parseJsonRoutes(rawJson);
        return !routes.empty();
    }

    bool saveBestIndividualToDb(const HgsDbConfig& cfg, const Individual& indiv, double elapsedTime) {
        if(cfg.dbPath.empty()) {
            return false;
        }

        // 只写入可行解，避免不可行解污染数据库
        if(!indiv.isFeasible) {
            std::cerr << "[HGS-DB] Skipping infeasible solution (penalizedCost=" << indiv.cost.penalizedCost 
                      << ", distance=" << indiv.cost.distance << ")\n";
            return false;
        }

        sqlite3* db = nullptr;
        char* errMsg = nullptr;

        int rc = sqlite3_open_v2(cfg.dbPath.c_str(), &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE, nullptr);
        if(rc != SQLITE_OK) {
            std::cerr << "[HGS-DB] Can't open database: " << sqlite3_errmsg(db) << "\n";
            sqlite3_close(db);
            return false;
        }

        sqlite3_busy_timeout(db, 30000);
        sqlite3_exec(db, "PRAGMA journal_mode=WAL;", nullptr, nullptr, nullptr);
        sqlite3_exec(db, "PRAGMA synchronous=NORMAL;", nullptr, nullptr, nullptr);

        const char* createSql =
            "CREATE TABLE IF NOT EXISTS solution_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, algo_name TEXT, score REAL, solution TEXT, runningtime REAL);"
            "CREATE TABLE IF NOT EXISTS global_best ("
            "id INTEGER PRIMARY KEY, algo_name TEXT, score REAL, solution TEXT, runningtime REAL);"
            "INSERT OR IGNORE INTO global_best (id, score) VALUES (1, 1e20);";

        rc = sqlite3_exec(db, createSql, nullptr, nullptr, &errMsg);
        if(rc != SQLITE_OK) {
            std::cerr << "[HGS-DB] Init tables failed: " << errMsg << "\n";
            sqlite3_free(errMsg);
            sqlite3_close(db);
            return false;
        }

        // Build routes vector from the individual, ignoring empty routes.
        std::vector<std::vector<int>> routes;
        routes.reserve(indiv.routes.size());
        for(const auto& r : indiv.routes) {
            if(!r.empty()) {
                routes.push_back(r);
            }
        }

        const std::string solJson = routesToJsonString(routes);
        // 对于可行解，penalizedCost 和 distance 几乎相等，使用 penalizedCost 保持一致性
        const double score = indiv.cost.penalizedCost;

        // Begin Transaction
        sqlite3_exec(db, "BEGIN IMMEDIATE", nullptr, nullptr, nullptr);

        // Insert History (无条件插入，与 FILO2 逻辑一致)
        sqlite3_stmt* stmt = nullptr;
        const char* insSql =
            "INSERT INTO solution_history (algo_name, score, solution, runningtime) VALUES (?, ?, ?, ?)";
        sqlite3_prepare_v2(db, insSql, -1, &stmt, nullptr);
        sqlite3_bind_text(stmt, 1, cfg.algoName.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(stmt, 2, score);
        sqlite3_bind_text(stmt, 3, solJson.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(stmt, 4, elapsedTime);

        if(sqlite3_step(stmt) != SQLITE_DONE) {
            std::cerr << "[HGS-DB] Insert history failed: " << sqlite3_errmsg(db) << "\n";
        }
        sqlite3_finalize(stmt);

        // Update Global Best (Minimization: update if New Score < Old Score)
        // Note: The SQL ensures atomic check-and-update
        const char* updSql =
            "UPDATE global_best SET score = ?, solution = ?, algo_name = ?, runningtime = ? "
            "WHERE id = 1 AND score > ?";

        sqlite3_prepare_v2(db, updSql, -1, &stmt, nullptr);
        sqlite3_bind_double(stmt, 1, score);
        sqlite3_bind_text(stmt, 2, solJson.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_text(stmt, 3, cfg.algoName.c_str(), -1, SQLITE_TRANSIENT);
        sqlite3_bind_double(stmt, 4, elapsedTime);
        sqlite3_bind_double(stmt, 5, score); // Check logic: score > new_score

        rc = sqlite3_step(stmt);
        bool updated = (sqlite3_changes(db) > 0);
        sqlite3_finalize(stmt);

        // Commit
        if(rc == SQLITE_DONE) {
            sqlite3_exec(db, "COMMIT", nullptr, nullptr, nullptr);
        } else {
            std::cerr << "[HGS-DB] Update failed: " << sqlite3_errmsg(db) << "\n";
            sqlite3_exec(db, "ROLLBACK", nullptr, nullptr, nullptr);
        }

        sqlite3_close(db);
        return true;
    }

} // namespace genvrp


