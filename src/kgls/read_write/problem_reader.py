import os

from ..datastructure import Node, VRPProblem


def read_vrp_instance(file_path: str) -> VRPProblem:
    nodes = dict()
    capacity: int = 0

    with open(file_path, 'r') as file:
        current_section = None
        for line in file:
            line = line.strip()

            if line == '':
                continue

            if line.startswith("CAPACITY"):
                capacity = int(line.split(':')[1].strip())

            elif not line[0].isdigit():
                current_section = line
                continue

            elif current_section == "NODE_COORD_SECTION":
                parts = line.split()
                node_id = int(parts[0]) #- 1  # assuming IDs start with 1
                x = float(parts[1])
                y = float(parts[2])
                nodes[node_id] = {
                    'id': node_id,
                    'x': x,
                    'y': y
                }

            elif current_section == "DEMAND_SECTION":
                parts = line.split()
                node_id = int(parts[0].strip()) #- 1
                demand = int(parts[1].strip())
                # assume that demand section is after coord section
                nodes[node_id].update({
                    'demand': demand
                })

            elif line == "EOF":
                break

        # also try read the best known solution
        sol_file_path = file_path.replace('.vrp', '.sol')
        if os.path.exists(sol_file_path):
            best_solution = read_best_known_solution(sol_file_path)
        else:
            best_solution = float('inf')

    vrp_nodes = [
        Node(
            node_id=node['id'],
            x_coordinate=node['x'],
            y_coordinate=node['y'],
            demand=node['demand'],
            is_depot=node['demand'] == 0,
        )
        for node in nodes.values()
    ]
    return VRPProblem(
        nodes=vrp_nodes,
        capacity=capacity,
        bks=best_solution
    )


def read_best_known_solution(file_path: str) -> float:
    cost = float('inf')
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()

            if line.startswith('Cost'):
                parts = line.split()
                cost = int(parts[1].strip())

    return cost
