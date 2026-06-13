"""MapReduce-style K-Means adapted from HW2 (hw2/hw_r14921059)."""

from __future__ import annotations

import multiprocessing
from queue import Empty

import numpy as np


class KMeansMapper(multiprocessing.Process):
    def __init__(self, data_chunk, centroids, result_queue):
        super().__init__()
        self.data_chunk = data_chunk
        self.centroids = centroids
        self.result_queue = result_queue

    def run(self):
        if not self.centroids:
            return

        centroids = [np.asarray(centroid, dtype=float) for centroid in self.centroids]

        for idx, centroid in enumerate(centroids):
            self.result_queue.put(("__centroid__", idx, centroid))

        for point in self.data_chunk:
            point = np.asarray(point, dtype=float)
            distances = [np.sum((point - centroid) ** 2) for centroid in centroids]
            nearest_centroid_idx = int(np.argmin(distances))
            self.result_queue.put((nearest_centroid_idx, point))


class KMeansReducer(multiprocessing.Process):
    def __init__(self, result_queue, num_clusters, new_centroids):
        super().__init__()
        self.result_queue = result_queue
        self.num_clusters = num_clusters
        self.new_centroids = new_centroids

    def run(self):
        cluster_sums = [None] * self.num_clusters
        cluster_counts = [0] * self.num_clusters
        previous_centroids = {}
        point_dim = None

        while True:
            try:
                item = self.result_queue.get(timeout=0.1)
            except Empty:
                break

            if len(item) == 3 and item[0] == "__centroid__":
                _, cluster_idx, centroid = item
                previous_centroids.setdefault(cluster_idx, np.asarray(centroid, dtype=float))
                if point_dim is None:
                    point_dim = previous_centroids[cluster_idx].shape[0]
                continue

            cluster_idx, point = item
            point = np.asarray(point, dtype=float)

            if point_dim is None:
                point_dim = point.shape[0]

            if cluster_sums[cluster_idx] is None:
                cluster_sums[cluster_idx] = np.zeros_like(point, dtype=float)

            cluster_sums[cluster_idx] += point
            cluster_counts[cluster_idx] += 1

        if point_dim is None:
            return

        for cluster_idx in range(self.num_clusters):
            if cluster_counts[cluster_idx] > 0:
                self.new_centroids[cluster_idx] = (
                    cluster_sums[cluster_idx] / cluster_counts[cluster_idx]
                )
            elif cluster_idx in previous_centroids:
                self.new_centroids[cluster_idx] = previous_centroids[cluster_idx]
            else:
                self.new_centroids[cluster_idx] = np.zeros(point_dim, dtype=float)


def split_data(data, num_chunks):
    chunk_size = len(data) // num_chunks + 1
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]


def run_mapreduce_kmeans(
    points: list[np.ndarray],
    num_clusters: int = 4,
    num_mappers: int = 4,
    max_iter: int = 10,
) -> tuple[list[np.ndarray], list[int]]:
    """Return final centroids and cluster assignment for each point."""
    if len(points) < num_clusters:
        raise ValueError(
            f"Need at least {num_clusters} points for K-Means, got {len(points)}"
        )

    rng = np.random.default_rng(42)
    init_indices = rng.choice(len(points), num_clusters, replace=False)
    centroids = [np.asarray(points[i], dtype=float) for i in init_indices]

    assignments: list[int] = [0] * len(points)

    for _ in range(max_iter):
        data_chunks = split_data(points, min(num_mappers, len(points)))
        result_queue = multiprocessing.Queue()

        mappers = [KMeansMapper(chunk, centroids, result_queue) for chunk in data_chunks]
        for mapper in mappers:
            mapper.start()
        for mapper in mappers:
            mapper.join()

        manager = multiprocessing.Manager()
        new_centroids = manager.dict()
        reducer = KMeansReducer(result_queue, num_clusters, new_centroids)
        reducer.start()
        reducer.join()

        updated = [new_centroids[i] for i in range(num_clusters)]
        if np.allclose(centroids, updated, atol=1e-4):
            centroids = updated
            break
        centroids = updated

    final_centroids = [np.asarray(c, dtype=float) for c in centroids]
    for idx, point in enumerate(points):
        point_arr = np.asarray(point, dtype=float)
        distances = [np.sum((point_arr - c) ** 2) for c in final_centroids]
        assignments[idx] = int(np.argmin(distances))

    return final_centroids, assignments
