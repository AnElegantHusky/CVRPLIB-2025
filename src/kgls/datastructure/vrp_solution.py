from collections import defaultdict

from .node import Node
from .route import Route
from .vrp_problem import VRPProblem
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


class VRPSolution:
    def __init__(self, problem: VRPProblem):
        self._next_route_index = 0
        self.routes = []
        self.problem = problem
        self.solution_stats: defaultdict[str, float] = defaultdict(float)
        self._plot_progress = False

        self._prev: dict[int, int] = {
            node.node_id: None
            for node in self.problem.customers
        }
        self._next: dict[int, int] = {
            node.node_id: None
            for node in self.problem.customers
        }
        self._route: dict[int, int] = {
            node.node_id: None
            for node in self.problem.customers
        }

    def start_plotting(self):
        self._plot_progress = True

        self._fig = plt.figure(figsize=(10, 6))
        gs = GridSpec(3, 4, figure=self._fig)  # 3 rows, 4 columns grid
        self._ax_routes = self._fig.add_subplot(gs[:, :3])  # Large panel for routes
        self._ax_chart = self._fig.add_subplot(gs[0, 3])  # Small panel for chart
        self._time_steps = []
        self._solution_values = []

        plt.ion()

        self._node_scatter = None
        self._plotted_edges = []

        self._initialize_plots()
        plt.show()

    def prev(self, node_index: Node) -> Node:
        return self._prev[node_index.node_id]

    def next(self, node_index: Node) -> Node:
        return self._next[node_index.node_id]

    def route_of(self, node: Node) -> Route:
        return self._route[node.node_id]

    def neighbour(self, node_index: Node, direction: int) -> Node:
        if direction == 0:
            return self.prev(node_index)
        else:
            return self.next(node_index)

    def validate(self):
        # All routes are OK
        for route in self.routes:
            route.validate()

        for route in self.routes:
            assert route.volume <= self.problem.capacity, \
                "Capacity violation"
            for node in route.customers:
                assert self._route[node.node_id] == route

        # check that nodes are linked correctly
        for route in self.routes:
            if route.size > 0:
                assert self.prev(route._nodes[1]) == route.depot
                assert self.next(route._nodes[-2]) == route.depot

        for node in self.problem.nodes:
            if not node.is_depot and not self.prev(node).is_depot:
                assert self.next(self.prev(node)) == node
            if not node.is_depot and not self.next(node).is_depot:
                assert self.prev(self.next(node)) == node

        # All customers have been visited exactly once
        visited_customers = []

        for route in self.routes:
            visited_customers.extend(
                route.customers
            )

        assert len(visited_customers) == len(set(visited_customers)), \
            "Some customers have been planned more than once"

        assert len(visited_customers) == len(self.problem.customers), \
            "Not all customers have been planned"

    def copy(self):
        solution_copy = self.__class__(self.problem)
        for route in self.routes:
            solution_copy.add_route(route.customers.copy())

        return solution_copy

    def to_file(self, path_to_file: str):
        "按照所有id都-1的方式存储"
        with open(path_to_file, 'w') as file:
            # 依次保存每条路径，按照 "Route #n: ..." 的格式
            for idx, route in enumerate(self.routes, 1):
                if route.size > 0:
                    # 将当前路径的节点id用空格连接，按指定格式写入
                    route_str = f"Route #{idx}: " + " ".join(
                        str(node.node_id - 1) for node in route.nodes_without_depot)  # 假设node_id是节点的标识符
                    file.write(route_str + '\n')

    def remove_nodes(self, nodes_to_be_removed: list[Node]):
        route = self.route_of(nodes_to_be_removed[0])

        # nodes might be reversed
        if len(nodes_to_be_removed) > 1 and self.next(nodes_to_be_removed[0]) != nodes_to_be_removed[1]:
            prev_left_neighbor = self.prev(nodes_to_be_removed[-1])
            prev_right_neighbor = self.next(nodes_to_be_removed[0])
        else:
            prev_left_neighbor = self.prev(nodes_to_be_removed[0])
            prev_right_neighbor = self.next(nodes_to_be_removed[-1])

        self._next[prev_left_neighbor.node_id] = prev_right_neighbor
        self._prev[prev_right_neighbor.node_id] = prev_left_neighbor

        for node in nodes_to_be_removed:
            self._route[node.node_id] = None
            route.remove_customer(node)

    def add_route(self, nodes: list[Node]):
        new_depot = self.problem.depot
        route_nodes = [new_depot] + nodes + [new_depot]

        new_route = Route(route_nodes, self._next_route_index)
        self.routes.append(new_route)

        self._next_route_index += 1

        for idx, node in enumerate(route_nodes):
            if not node.is_depot:
                self._prev[node.node_id] = route_nodes[idx - 1]
                self._next[node.node_id] = route_nodes[idx + 1]
                self._route[node.node_id] = new_route

    def insert_nodes_after(self, nodes_to_be_inserted: list[Node], move_after_node: Node, route: Route):
        # re-link the nodes to be inserted, since they might have been rotated
        for index, node in enumerate(nodes_to_be_inserted):
            if index + 1 < len(nodes_to_be_inserted):
                self._next[node.node_id] = nodes_to_be_inserted[index + 1]
                self._prev[nodes_to_be_inserted[index + 1].node_id] = node
            self._route[node.node_id] = route

        # add links between new nodes and connecting nodes in route
        if move_after_node.is_depot:
            old_next_node = route._nodes[1]
        else:
            old_next_node = self.next(move_after_node)
        self._next[move_after_node.node_id] = nodes_to_be_inserted[0]
        self._prev[nodes_to_be_inserted[0].node_id] = move_after_node

        self._next[nodes_to_be_inserted[-1].node_id] = old_next_node
        self._prev[old_next_node.node_id] = nodes_to_be_inserted[-1]

        route.add_customers_after(nodes_to_be_inserted, move_after_node)

    def rearrage_route(self, route: Route, node_order: list[Node]):
        assert node_order[0].is_depot
        assert node_order[-1].is_depot

        for idx, node in enumerate(node_order):
            if not node.is_depot:
                self._prev[node.node_id] = node_order[idx - 1]
                self._next[node.node_id] = node_order[idx + 1]

        route._nodes = node_order
        self.validate()

    def _initialize_plots(self):
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec

        # Initialize route lines
        colors = plt.cm.get_cmap("tab20c")
        for route_index in range(len(self.problem.customers)):  # max number of possible routes
            line, = self._ax_routes.plot([], [], color=colors(route_index % 20))
            self._plotted_edges.append(line)

        # draw nodes
        for node in self.problem.nodes:
            if node.is_depot:
                self._ax_routes.plot(node.x_coordinate, node.y_coordinate, color='black', marker='s')
            else:
                self._ax_routes.plot(node.x_coordinate, node.y_coordinate, color='grey', marker='o')

        self._ax_routes.axis('off')

        # layout of chart
        self._ax_chart.set_box_aspect(1)  # Make the chart square-ish
        self._ax_chart.spines['top'].set_visible(False)
        self._ax_chart.spines['right'].set_visible(False)
        self._ax_chart.spines['bottom'].set_color('grey')
        self._ax_chart.spines['left'].set_color('grey')
        self._ax_chart.grid(False)
        self._ax_chart.set_xticks([])
        self._ax_chart.set_yticks([])

        self._chart_line, = self._ax_chart.plot([], [], label="", color='black', linewidth=1)

        self._fig.canvas.draw()
        self._fig.canvas.flush_events()

    def plot(self, solution_value: float):
        if self._plot_progress:
            # update routes
            for route_index, route in enumerate(self.routes):
                x_coordinates = [route.depot.x_coordinate] + [node.x_coordinate for node in route.nodes]
                y_coordinates = [route.depot.y_coordinate] + [node.y_coordinate for node in route.nodes]
                self._plotted_edges[route_index].set_data(x_coordinates, y_coordinates)

            # update value chart
            if self.problem.bks != float('inf'):
                current_gap = 100 * (solution_value - self.problem.bks) / self.problem.bks
            else:
                current_gap = solution_value

            self._time_steps.append(len(self._time_steps) + 1)
            self._solution_values.append(current_gap)
            self._chart_line.set_data(self._time_steps, self._solution_values)
            self._ax_chart.relim()  # Recompute the axis limits
            self._ax_chart.autoscale_view()
            self._ax_chart.set_title(f'Gap to Optimum: {current_gap: .2f}%', fontsize=10, loc='center')

            self._fig.canvas.draw_idle()
            self._fig.canvas.flush_events()

            # only to create a .gif afterwards
            # plt.savefig(f'pics/pic_{str(len(self._solution_values)).zfill(4)}.png')
