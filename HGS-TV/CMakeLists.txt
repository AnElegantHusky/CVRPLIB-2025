cmake_minimum_required(VERSION 3.15.0)
project(hgs_tv VERSION 0.0.1 LANGUAGES C CXX)
list(INSERT CMAKE_MODULE_PATH 0 ${CMAKE_CURRENT_SOURCE_DIR})

set(WARNING_OPTIONS             -Wall -Wextra -Werror)
set(RELEASE_OPTIONS             -O3 -march=native -mtune=native)
set(DEBUG_OPTIONS               -O0 -g)
set(GDB_DEBUG_OPTIONS           -ggdb)
set(LINKER_OPTIONS              -flto)

add_compile_options(${WARNING_OPTIONS})
add_compile_options("$<$<CONFIG:RELEASE>:${RELEASE_OPTIONS}>")
add_compile_options("$<$<CONFIG:DEBUG>:${DEBUG_OPTIONS}>")
add_compile_options("$<$<AND:$<CONFIG:DEBUG>,$<CXX_COMPILER_ID:GNU>>:${GDB_DEBUG_OPTIONS}>")
add_compile_definitions("$<$<AND:$<CONFIG:DEBUG>,$<CXX_COMPILER_ID:GNU>>:${GCC_DEBUG_DEFINES}>")

add_executable(hgs
        # 核心源文件
        src/CommandLineParser.cpp
        src/DecompositionMethod.cpp
        src/Genetic.cpp
        src/Individual.cpp
        src/LocalSearch.cpp
        src/main.cpp
        src/Params.cpp
        src/Population.cpp
        src/Split.cpp
        src/SubProblem.cpp

        # 分解方法实现
        src/Decomposition/ArcBasedDecomposition.cpp
        src/Decomposition/ArcBased/ArcHistoryDecomposition.cpp
        src/Decomposition/RouteSequence/BarycentreClusteringDecomposition.cpp
        src/Decomposition/RouteSequence/BarycentreQuadrantDecomposition.cpp
        src/Decomposition/RouteSequence/BarycentreSwipeDecomposition.cpp
        src/Decomposition/ArcBased/CostArcDecomposition.cpp
        src/Decomposition/ArcBased/CostPathDecomposition.cpp
        src/Decomposition/ArcBased/RandomPathDecomposition.cpp
        src/Decomposition/ArcBased/RandomArcDecomposition.cpp
        src/Decomposition/RouteSequence/RandomRouteDecomposition.cpp
        src/Decomposition/RouteSequence/RouteHistoryDecomposition.cpp
        src/Decomposition/RouteSequenceDecomposition.cpp
        src/Decomposition/ArcBased/PathHistoryDecomposition.cpp

        # SQLite 协作适配器
        src/solution/HgsDbAdapter.cpp

        # 内置 sqlite3 实现（单文件版）
        src/include/sqlite3.c
)

target_include_directories(hgs PRIVATE src/include)

target_compile_features(hgs PRIVATE cxx_std_17)
target_link_libraries(hgs PRIVATE pthread)
target_link_libraries(hgs PRIVATE dl)
target_compile_options(hgs PRIVATE -Wno-sign-compare)

option(BATCH_MODE "Suppress printing to stdout, for running experiments on clusters." OFF)
if(BATCH_MODE)
    target_compile_definitions(hgs PRIVATE BATCH_MODE)
endif()