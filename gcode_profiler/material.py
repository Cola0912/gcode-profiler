# -*- coding: utf-8 -*-
"""
素材(フィラメント材質)推定
==========================
ノズル温度・ベッド温度・チャンバー温度の組み合わせから、使用された素材を推定する。
温度帯は重複するため、断定ではなくスコア上位候補と信頼度を返す。
"""
from __future__ import annotations

# (nozzle_lo, nozzle_hi, bed_lo, bed_hi, chamber_pref)
#   chamber_pref: None=不問 / "warm"=加温推奨 / "hot"=高温必須
_PROFILES = {
    "PLA":        (185, 225, 0, 65, None),
    "PETG":       (225, 255, 60, 90, None),
    "TPU":        (200, 240, 25, 60, None),
    "ABS":        (230, 265, 90, 110, "warm"),
    "ASA":        (235, 265, 90, 110, "warm"),
    "PP":         (220, 255, 80, 105, None),
    "PA (Nylon)": (240, 295, 60, 100, None),
    "PA-CF":      (260, 320, 70, 110, "warm"),
    "PC":         (260, 310, 100, 130, "warm"),
    "PC-CF":      (270, 315, 100, 130, "warm"),
    "PPS / PPS-CF": (300, 345, 110, 150, "hot"),
    "PEI/ULTEM":  (340, 400, 130, 170, "hot"),
    "PEKK":       (340, 385, 120, 160, "hot"),
    "PEEK":       (360, 460, 120, 170, "hot"),
}

# 候補一覧(GUI のプルダウン用)
MATERIAL_CHOICES = ["PLA", "PETG", "ABS", "ASA", "TPU", "PP", "PA (Nylon)", "PA-CF",
                    "PC", "PC-CF", "PPS / PPS-CF", "PEKK", "PEI/ULTEM", "PEEK", "その他"]


def _box_score(v, lo, hi, soft=20.0):
    """v が [lo,hi] 内なら 1.0、外側は soft 幅で線形に減衰。"""
    if v is None:
        return None
    if lo <= v <= hi:
        return 1.0
    d = (lo - v) if v < lo else (v - hi)
    return max(0.0, 1.0 - d / soft)


def estimate_material(nozzle_temp=None, bed_temp=None, chamber_temp=None):
    """温度から素材を推定。返り値: dict(material, confidence, candidates[])。"""
    if nozzle_temp is None:
        return {"material": None, "confidence": 0,
                "candidates": [], "reason": "ノズル温度が不明のため素材推定不可"}

    scored = []
    for name, (nlo, nhi, blo, bhi, ch) in _PROFILES.items():
        ns = _box_score(nozzle_temp, nlo, nhi, soft=25)
        score = ns * 0.7
        weight = 0.7
        bs = _box_score(bed_temp, blo, bhi, soft=30)
        if bs is not None:
            score += bs * 0.2
            weight += 0.2
        # チャンバー整合
        cs = 0.5
        if ch == "hot":
            cs = 1.0 if (chamber_temp and chamber_temp >= 70) else (0.6 if chamber_temp is None else 0.3)
        elif ch == "warm":
            cs = 1.0 if (chamber_temp and chamber_temp >= 35) else (0.7 if chamber_temp is None else 0.6)
        else:
            cs = 1.0 if not chamber_temp else 0.8
        score += cs * 0.1
        weight += 0.1
        scored.append((name, score / weight))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:3]
    best_name, best_score = top[0]
    second = top[1][1] if len(top) > 1 else 0.0

    conf = best_score * 70
    if bed_temp is not None:
        conf += 10
    if chamber_temp is not None:
        conf += 5
    if best_score - second > 0.2:
        conf += 10
    conf = int(max(0, min(100, round(conf))))

    return {
        "material": best_name,
        "confidence": conf,
        "candidates": [{"name": n, "score": round(s, 3)} for n, s in top],
        "reason": f"ノズル {nozzle_temp:.0f}℃"
                  + (f" / ベッド {bed_temp:.0f}℃" if bed_temp else "")
                  + (f" / チャンバー {chamber_temp:.0f}℃" if chamber_temp else "")
                  + f" → {best_name} の温度帯に最も整合",
    }
