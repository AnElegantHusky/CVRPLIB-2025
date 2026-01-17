# base_path
#    - Competition_Deploy_Hybird
#        - all_in_one
#            - SISR
#                - log_buffer
#                    - XL-xxx-xxx
#                        - shared.db
#            - ...
#    - Warm_Start_Deploy_Hybrid
#        - all_in_one
#            - SISR




MAIN_ROOT_PATH = "Competition_Deploy_Hybird/all_in_one/SISR/"
WARM_START_ROOT_PATH = "Warm_Start_Deploy_Hybrid/all_in_one/SISR/"

LOG_BUFFER_DIR = "log_buffer/"

servers = [
    {
        "host": "10.90.91.100",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (0, 3),
    },
    {
        "host": "10.90.91.101",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (3, 9),
    },
    {
        "host": "10.90.91.124",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (9, 15),
    },
    {
        "host": "10.90.91.125",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (15, 21),
    },
    {
        "host": "10.90.91.126",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (21, 27),
    },
    {
        "host": "10.90.91.127",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (27, 32),
    },
    {
        "host": "10.90.91.163",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (32, 37),
    },
    {
        "host": "10.90.91.167",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/",
        "instance_range": (37, 42),
    },
    {
        "host": "10.90.91.49",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/",
        "instance_range": (42, 49),
    },
    {
        "host": "10.90.91.51",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/",
        "instance_range": (49, 56),
    },
    {
        "host": "10.90.91.231",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/",
        "instance_range": (56, 78),
    },
    {
        "host": "10.90.91.232",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/",
        "instance_range": (78, 100),
    },
]