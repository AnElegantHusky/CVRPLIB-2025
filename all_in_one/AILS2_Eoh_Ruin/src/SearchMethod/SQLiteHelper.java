package SearchMethod;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;

import java.lang.reflect.Type;
import java.sql.*;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class SQLiteHelper {
    private static final String DB_URL_PREFIX = "jdbc:sqlite:";

    // Gson 实例
    private static final Gson gson = new GsonBuilder()
            .disableHtmlEscaping()
            .serializeNulls()
            .create();

    /**
     * 获取带有配置参数的数据库连接 URL
     * 对应功能：
     * 1. journal_mode=WAL (开启并发写)
     * 2. busy_timeout=30000 (忙碌等待 30秒)
     */
    private static String getConnectionString(String dbPath) {
        // 直接在 URL 后追加参数是 sqlite-jdbc 的标准配置方式
        return DB_URL_PREFIX + dbPath + "?journal_mode=WAL&busy_timeout=30000";
    }

    /**
     * 保存最优解到数据库
     * 利用 SQLite 3.24+ 的 Upsert (ON CONFLICT) 语法实现原子更新
     *
     * @param solution 可以是 Java List/Object，也可以是 Python 格式的 String
     */
    public static boolean saveBest(String dbPath, double runningTime, double score,
                                   Object solution, String algoName) {
        String url = getConnectionString(dbPath);

        // 1. 处理 Solution：如果是字符串则假定已格式化好，否则用 Gson 序列化
        String solJson;
        if (solution instanceof String) {
            solJson = (String) solution;
        } else {
            solJson = gson.toJson(solution);
        }

        try (Connection conn = DriverManager.getConnection(url)) {
            // 开启事务以提高性能
            conn.setAutoCommit(false);

            try (Statement stmt = conn.createStatement()) {
                // --- A. 插入历史记录 (无条件插入) ---
                String historySql = "INSERT INTO solution_history (algo_name, score, solution, runningtime) VALUES (?, ?, ?, ?)";
                try (PreparedStatement pstmt = conn.prepareStatement(historySql)) {
                    pstmt.setString(1, algoName);
                    pstmt.setDouble(2, score);
                    pstmt.setString(3, solJson);
                    pstmt.setDouble(4, runningTime);
                    pstmt.executeUpdate();
                }

                // --- B. 更新全局最优 (Upsert 逻辑) ---
                // 解释：尝试插入 id=1。如果 id 冲突（已存在），且新分数 < 旧分数，则更新字段。
                // 要求 global_best 表的 id 字段必须是 PRIMARY KEY 或 UNIQUE
                String upsertSql = "INSERT INTO global_best (id, score, solution, algo_name, runningtime) " +
                        "VALUES (1, ?, ?, ?, ?) " +
                        "ON CONFLICT(id) DO UPDATE SET " +
                        "score = excluded.score, " +
                        "solution = excluded.solution, " +
                        "algo_name = excluded.algo_name, " +
                        "runningtime = excluded.runningtime " +
                        "WHERE excluded.score < global_best.score"; // 仅当新分数更优(更小)时才更新

                try (PreparedStatement pstmt = conn.prepareStatement(upsertSql)) {
                    pstmt.setDouble(1, score);
                    pstmt.setString(2, solJson);
                    pstmt.setString(3, algoName);
                    pstmt.setDouble(4, runningTime);
                    pstmt.executeUpdate();
                }

                conn.commit();
                return true;

            } catch (SQLException e) {
                conn.rollback();
                throw e;
            }
        } catch (SQLException e) {
            System.err.println("[DB Error] " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }

    public static boolean saveAcceptanceParams(String dbPath, String algoName, int k, int iteration, double eta, double omega) {
        String url = getConnectionString(dbPath); // 假设 getConnectionString 已定义

        // 定义表结构：如果不存在则创建
        String createTableSql = "CREATE TABLE IF NOT EXISTS acceptance_history (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "algo_name TEXT, " +
                "global_iterator INTEGER, " +
                "eta REAL, " +
                "omega REAL, " +
                "k INTEGER " +
                ");";

        // 插入数据的 SQL
        String insertSql = "INSERT INTO acceptance_history" +
                "(id, algo_name, global_iterator, eta, omega, k) " +
                "VALUES (1, ?, ?, ?, ?, ?) " +
                "ON CONFLICT(id) DO UPDATE SET " +
                "algo_name = EXCLUDED.algo_name, " +
                "global_iterator = EXCLUDED.global_iterator, " +
                "eta = EXCLUDED.eta, " +
                "omega = EXCLUDED.omega, " +
                "k = EXCLUDED.k";

        try (Connection conn = DriverManager.getConnection(url)) {
            conn.setAutoCommit(false); // 开启事务

            try (Statement stmt = conn.createStatement()) {
                // 1. 确保表存在
                stmt.execute(createTableSql);

                // 2. 插入参数记录
                try (PreparedStatement pstmt = conn.prepareStatement(insertSql)) {
                    pstmt.setString(1, algoName);
                    pstmt.setInt(2, iteration);
                    pstmt.setDouble(3, eta);
                    pstmt.setDouble(4, omega);
                    pstmt.setInt(5, k);

                    pstmt.executeUpdate();
                }

                conn.commit();
                return true;

            } catch (SQLException e) {
                conn.rollback();
                throw e;
            }
        } catch (SQLException e) {
            System.err.println("[DB Error - AcceptanceCriterion] " + e.getMessage());
            e.printStackTrace();
            return false;
        }
    }


    /**
     * 加载最优解
     * 使用 Gson 将 JSON 字符串反序列化为 Java List
     */
    public static Map<String, Object> loadBest(String dbPath) {

        String url = getConnectionString(dbPath);
        String sql = "SELECT score, solution, algo_name, runningtime FROM global_best WHERE id=1";

        try (Connection conn = DriverManager.getConnection(url);
             PreparedStatement pstmt = conn.prepareStatement(sql);
             ResultSet rs = pstmt.executeQuery()) {

            if (rs.next()) {
                double score = rs.getDouble("score");
                String solJson = rs.getString("solution");

                if (solJson != null && !solJson.isEmpty() && !solJson.equals("None")) {
                    Map<String, Object> result = new HashMap<>();
                    result.put("score", score);
                    result.put("algo_name", rs.getString("algo_name"));
                    result.put("runningtime", rs.getDouble("runningtime"));

                    // --- 核心转换逻辑 ---
                    List<Integer> flatSolution = parseNestedJsonToFlatList(solJson);
                    result.put("solution", flatSolution);

                    return result;
                }
            }
            return null;

        } catch (SQLException e) {
            System.err.println("[DB Read Error] " + e.getMessage());
            return null;
        }
    }

    /**
     * 核心转换器：嵌套 JSON -> 扁平 List<Integer>
     * * 例子:
     * 输入: "[[1, 2], [3, 4]]"
     * 输出: [0, 1, 2, 0, 3, 4, 0]
     */
    private static List<Integer> parseNestedJsonToFlatList(String json) {
        List<Integer> flatList = new ArrayList<>();

        try {
            // 1. 定义类型：List<List<Number>>
            // 使用 Number 是为了兼容 Integer 和 Double (Gson 默认可能会把 1 解析为 1.0)
            Type nestedListType = new TypeToken<List<List<Number>>>(){}.getType();

            // 2. 解析 JSON
            List<List<Number>> nestedRoutes = gson.fromJson(json, nestedListType);

            // 3. 开始扁平化
            if (nestedRoutes != null) {
                // 必须以 Depot (0) 开始
                flatList.add(0);

                for (List<Number> route : nestedRoutes) {
                    // 如果路径不为空，才处理
                    if (route != null && !route.isEmpty()) {
                        for (Number node : route) {
                            // 将 Number 转为 int (例如 1.0 -> 1)
                            flatList.add(node.intValue());
                        }
                        // 每条路径结束后，必须回到 Depot (0)
                        flatList.add(0);
                    }
                }

                // 校验：确保列表至少包含 [0, 0] 结构（如果原本只有一条空路径）
                // 上面的逻辑保证了只要有 route 就会以 0 结尾，所以通常不需要额外补
                // 但为了保险，检查最后一位是否是 0
                if (!flatList.isEmpty() && flatList.get(flatList.size() - 1) != 0) {
                    flatList.add(0);
                }
            }
        } catch (Exception e) {
            System.err.println("[Data Parse Error] Failed to parse JSON: " + json);
            e.printStackTrace();
            // 如果解析失败（例如格式不对），返回空列表防止空指针
            return new ArrayList<>();
        }

        return flatList;
    }
}