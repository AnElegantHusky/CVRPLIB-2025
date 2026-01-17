import json
import re


def parse_sol_file(file_path):
    """
    Parses a standard VRPLIB .sol file.
    Format example:
      Route 1: 1 5 10
      Cost 123.45

    Returns: (score, routes_list)
    """
    routes = []
    cost = float('inf')

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Parse Cost
                if line.lower().startswith('cost'):
                    parts = line.split()
                    for p in parts:
                        # Simple check for number
                        if p.replace('.', '', 1).isdigit():
                            cost = float(p)
                            break

                # Parse Route
                if line.lower().startswith('route'):
                    if ':' in line:
                        route_str = line.split(':')[1]
                        # Extract node numbers
                        route = [int(x) for x in route_str.split() if x.isdigit()]
                        if route:
                            routes.append(route)
    except Exception as e:
        print(f"[Error] Failed to parse {file_path}: {e}")
        return float('inf'), []

    return cost, routes


def routes_to_sol_string(routes, cost, instance_name="Unknown"):
    """
    Converts a list-of-lists route structure into standard .sol text.
    """
    lines = []
    # lines.append(f"Instance: {instance_name}") # Optional header
    for idx, route in enumerate(routes):
        route_str = " ".join(map(str, route))
        lines.append(f"Route {idx + 1}: {route_str}")
    lines.append(f"Cost {cost}")
    return "\n".join(lines)