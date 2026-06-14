# HW2 Integration

## What HW2 contains

The `hw2/` directory is your **MapReduce K-Means** homework:

- `hw2/hw_r14921059/mapper.py` — assigns points to nearest centroid
- `hw2/hw_r14921059/reducer.py` — recomputes centroid means
- `hw2/main.py` — orchestrates mapper/reducer iterations with multiprocessing

This is a **distributed batch processing** pattern from the course, not a demand-validation survey.

## How the final project uses it

The final project applies the same MapReduce pattern to rental analytics:

1. Ingest rental transactions (`scripts/ingest_open_data.py`)
2. Standardize features `(area_ping, rent_per_ping)`
3. Run MapReduce K-Means via `pipeline/mapreduce_kmeans.py` (adapted from HW2)
4. Label clusters as `budget / value / premium / luxury`
5. Expose results at `GET /api/clusters` and in the Streamlit dashboard

## Code lineage

| HW2 file | Final project file |
|----------|-------------------|
| `hw2/hw_r14921059/mapper.py` | `pipeline/mapreduce_kmeans.py` → `KMeansMapper` |
| `hw2/hw_r14921059/reducer.py` | `pipeline/mapreduce_kmeans.py` → `KMeansReducer` |
| `hw2/main.py` iteration loop | `pipeline/kmeans_segmentation.py` + `run_mapreduce_kmeans()` |

## Reproduce HW2 standalone

```bash
cd hw2/hw_r14921059
python ../main.py
```

## Reproduce K-Means inside LeasePulse

```bash
make run        # public-evidence + ingest + process (includes K-Means)
curl http://localhost:8000/clusters
```
