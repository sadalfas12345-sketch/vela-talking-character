# Pinch break telemetry

Captured by collect_pinch_telemetry.mjs with the original GLBs loaded read-only in Chromium. The test uses biological materials, Kp=90 N/m, Kd=0.08 N*s/m, implicit integration, and the existing 2% interocular drag. Samples include the held pinch and 1.2 seconds of release recovery.

| Model | Active vertices | Active triangles | Boundary edges | Peak max edge strain | Peak P95 edge strain | Peak boundary displacement | Boundary displacement / eye width | Minimum triangle-area ratio | Collapsed triangles | Orientation flips |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| female | 5,036 | 9,708 | 362 | 0.135609 | 0.003865 | 3.9504e-4 | 0.688% | 7.7745e-1 | 0 | 1 |
| male | 41,920 | 82,807 | 552 | 0.565104 | 0.002302 | 2.7209e-3 | 0.895% | 8.7465e-1 | 0 | 5 |

Boundary edges are selected-island edges used by exactly one selected-island triangle. Orientation flips are current-vs-neutral face-normal dot products below zero. Collapsed triangles have area ratio <= 1e-3. These are conservative geometry diagnostics; screenshots remain necessary for visual seams and spikes. The complete time series is in pinch-telemetry.json.
