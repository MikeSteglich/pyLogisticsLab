#runs in an env with fast_api
# the project directory (parent of this directory) contains logisticsLabCore, pyLogisticsLab and osm_data
export PYTHONPATH=$PYTHONPATH:"$(cd "$(dirname "$0")/.." && pwd)"
fastapi dev main.py
