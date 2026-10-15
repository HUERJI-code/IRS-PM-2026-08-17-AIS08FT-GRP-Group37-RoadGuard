"""RoadGuard Google 矩阵冒烟测试：建 3 个演示任务 -> 重算 -> 打印行程来源和各段时间。

用法（后端以 google_routes 启动后，另开窗口在仓库根目录运行）：
    python SystemCode/experiments/routing/google_smoke.py [--base http://127.0.0.1:8000]
只计 (3+1)^2 = 16 个 Google 元素；同一后端进程内重复运行会命中缓存，不再计费。
"""

import argparse
import io
import json
import sys
import uuid

import httpx
from PIL import Image

POINTS = [(1.332, 103.676), (1.346, 103.694), (1.3405, 103.706)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    base = parser.parse_args().base.rstrip("/") + "/api/v1"
    client = httpx.Client(timeout=120)

    stream = io.BytesIO()
    Image.new("RGB", (80, 40), "gray").save(stream, format="PNG")
    run = uuid.uuid4().hex[:8]
    for index, (lat, lon) in enumerate(POINTS):
        response = client.post(f"{base}/inspections", headers={"Idempotency-Key": f"smoke-{run}-{index}"},
                               files={"image": ("smoke.png", stream.getvalue(), "image/png")},
                               data={"metadata": json.dumps({
                                   "mode": "demo", "scenario_id": "high_confidence", "latitude": lat,
                                   "longitude": lon, "road_type": "public_motor_road"})})
        if response.status_code != 201:
            print("建任务失败:", response.status_code, response.text)
            return 1
        print("已建任务", response.json()["task_id"])

    revision = client.get(f"{base}/health").json()["input_revision"]
    response = client.post(f"{base}/route-plans/recalculate", json={"expected_revision": revision})
    if response.status_code != 200:
        print("重算失败:", response.status_code, json.dumps(response.json(), ensure_ascii=False, indent=2))
        return 1
    result = response.json()
    print(f"\n矩阵来源: {result['matrix_provider']}  模拟: {result['matrix_is_simulated']}  "
          f"取数时间: {result['matrix_generated_at']}  任务数: {result['task_count']}")
    for summary in result["plans"]:
        plan = client.get(f"{base}/route-plans/{summary['plan_id']}").json()
        print(f"\n[{plan['algorithm']}] 完工 {plan['metrics']['makespan_minutes']} 分钟, "
              f"总行程 {plan['metrics']['total_travel_minutes']} 分钟, 未分配 {len(plan['unassigned_tasks'])}")
        for route in plan["crew_routes"]:
            legs = " -> ".join(f"{s['task_id'][-6:]}({s['travel_minutes_from_previous']}min)" for s in route["stops"])
            back = route["return_travel_minutes"]
            print(f"  {route['crew_id']} {route['status']:<11} 基地 -> {legs or '无'}"
                  + (f" -> 基地({back}min)" if route["stops"] and back is not None else ""))
    if result["matrix_is_simulated"]:
        print("\n注意：这次用的是模拟矩阵，说明后端窗口没有设置 ROADGUARD_TRAVEL_MATRIX_PROVIDER=google_routes。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
