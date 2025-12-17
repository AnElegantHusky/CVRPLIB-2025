#ifndef HGS_DB_ADAPTER_H
#define HGS_DB_ADAPTER_H
/**
 *  Lightweight SQLite adapter for HGS-TV.
 *
 *  约定：
 *  - 使用与 FILO2 相同的数据库结构：
 *      global_best(id=1, score, solution, algo_name, runningtime)
 *      solution_history(id, algo_name, score, solution, runningtime)
 *  - solution 字段编码为 JSON 风格字符串：[[c11,c12,...],[c21,c22,...],...]
 *    不包含 depot，只包含客户编号。
 */

#include <string>
#include <vector>

namespace genvrp {

    class Individual;

    /** Configuration for the SQLite-based cooperation. */
    struct HgsDbConfig {
        std::string dbPath;    ///< Path to the shared SQLite database.
        std::string algoName;  ///< Name of this algorithm when writing to the DB (e.g., "HGS-TV").
    };

    /** Load the current global-best solution from the shared DB, if any.
     *
     *  On success, fills #routes with a list of routes (each route is a list of customers, without the depot),
     *  and #score with the associated objective value. Returns true if a valid solution was found.
     */
    bool loadBestRoutesFromDb(const HgsDbConfig& cfg, std::vector<std::vector<int>>& routes, double& score);

    /** Save a new best individual to the shared DB (append to history + update global_best if better).
     *
     *  @param cfg          DB configuration.
     *  @param indiv        Individual to serialise and save.
     *  @param elapsedTime  Elapsed time in seconds at which this best was found.
     *  @return             true if the operation completed without hard errors (even if no row was updated).
     */
    bool saveBestIndividualToDb(const HgsDbConfig& cfg, const Individual& indiv, double elapsedTime);

} // namespace genvrp

#endif // HGS_DB_ADAPTER_H


