
from ..datastructure import VRPProblem, VRPSolution


def read_vrp_solution(file_path: str, instance: VRPProblem) -> VRPSolution:
    solution = VRPSolution(instance)
    node_map = {node.node_id: node for node in instance.nodes}

    with open(file_path, 'r') as file:

        for line in file:
            route_str = line.strip()
            if not route_str:
                continue

            try:
                # Parse the line into a list of integers
                route = list(map(int, route_str.split('-')))
            except ValueError:
                raise ValueError(f"A route contains non-integer values: {route_str}")

            # load the nodes, if possible
            node_list = []

            for node_id in route:
                if node_id not in node_map:
                    raise ValueError(f"Node ID {node_id} in the route does not exist instance file.")
                node = node_map[node_id]

                if not node.is_depot:
                    node_list.append(node)

            solution.add_route(node_list)

    return solution
