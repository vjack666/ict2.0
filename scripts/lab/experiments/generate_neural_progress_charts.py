#!/usr/bin/env python3
"""Generate ICT SYSTEM neural training progress chart."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

plt.rcParams.update({
    'font.size': 10,
    'figure.facecolor': '#0f1117',
    'axes.facecolor': '#161a22',
    'axes.edgecolor': '#2d3340',
    'axes.labelcolor': '#c9d1d9',
    'xtick.color': '#8b949e',
    'ytick.color': '#8b949e',
    'text.color': '#e6edf3',
    'grid.color': '#2d3340',
    'grid.alpha': 0.4,
})

OUT = 'reports/audits/experiments/ai'
os.makedirs(OUT, exist_ok=True)

versions_all = ['v1.001', 'v1.002', 'v1.003', 'failure_anatomy_v1']
failure_recall = [0.0000, 0.0769, 0.2308, None]
failure_f1     = [0.0000, 0.1290, 0.2609, None]
accuracy       = [0.4500, 0.4474, 0.5132, None]
COLORS = ['#f85149', '#d29922', '#58a6ff', '#3fb950']

# ── MAIN COMBINED CHART 2x2 ──────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.patch.set_facecolor('#0f1117')

# TL: failure recall
ax = axes[0,0]
x = np.arange(len(versions_all))
vals = [v if v is not None else 0 for v in failure_recall]
bars = ax.bar(x, vals, color=COLORS, edgecolor='white', linewidth=0.8, width=0.6)
for i, (bar, v) in enumerate(zip(bars, failure_recall)):
    if v is None:
        ax.text(bar.get_x()+bar.get_width()/2, 0.015, 'PENDIENTE', ha='center', va='bottom', fontsize=9, color='#f0883e', weight='bold')
    else:
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.008, f'{v:.4f}', ha='center', va='bottom', fontsize=9, weight='bold', color='#e6edf3')
ax.set_xticks(x)
ax.set_xticklabels(versions_all, fontsize=9, rotation=15)
ax.set_ylabel('failure recall', fontsize=10)
ax.set_title('Failure Recall por versi\u00f3n', fontsize=12, pad=8)
ax.set_ylim(0, 0.30)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2f}'))
ax.grid(axis='y', alpha=0.3)
for sp in ['top','right']:
    ax.spines[sp].set_visible(False)

# TR: failure F1
ax = axes[0,1]
x = np.arange(3)
bars = ax.bar(x, failure_f1[:3], color=COLORS[:3], edgecolor='white', linewidth=0.8, width=0.55)
for bar, v in zip(bars, failure_f1[:3]):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.005, f'{v:.4f}', ha='center', va='bottom', fontsize=9, weight='bold', color='#e6edf3')
ax.set_xticks(x)
ax.set_xticklabels(versions_all[:3], fontsize=9, rotation=15)
ax.set_ylabel('failure F1', fontsize=10)
ax.set_title('Failure F1 por versi\u00f3n', fontsize=12, pad=8)
ax.set_ylim(0, 0.32)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2f}'))
ax.grid(axis='y', alpha=0.3)
for sp in ['top','right']:
    ax.spines[sp].set_visible(False)

# BL: accuracy
ax = axes[1,0]
x = np.arange(3)
bars = ax.bar(x, accuracy[:3], color=COLORS[:3], edgecolor='white', linewidth=0.8, width=0.55)
for bar, v in zip(bars, accuracy[:3]):
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.003, f'{v:.4f}', ha='center', va='bottom', fontsize=9, weight='bold', color='#e6edf3')
ax.set_xticks(x)
ax.set_xticklabels(versions_all[:3], fontsize=9, rotation=15)
ax.set_ylabel('accuracy', fontsize=10)
ax.set_title('Accuracy TEST_OOS por versi\u00f3n', fontsize=12, pad=8)
ax.set_ylim(0.40, 0.55)
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2f}'))
ax.grid(axis='y', alpha=0.3)
for sp in ['top','right']:
    ax.spines[sp].set_visible(False)

# BR: failure_anatomy splits
ax = axes[1,1]
splits = ['TRAIN', 'VALIDATION', 'TEST_OOS']
n_rows = [120, 96, 76]
n_fail = [25, 19, 26]
x = np.arange(len(splits))
width = 0.35
bars1 = ax.bar(x - width/2, n_rows, width, label='Total filas', color='#58a6ff', edgecolor='white', linewidth=0.6)
bars2 = ax.bar(x + width/2, n_fail, width, label='Failure', color='#f85149', edgecolor='white', linewidth=0.6)
for bar in bars1:
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1.5, str(int(bar.get_height())), ha='center', va='bottom', fontsize=9, weight='bold', color='#e6edf3')
for bar in bars2:
    ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1.5, str(int(bar.get_height())), ha='center', va='bottom', fontsize=9, weight='bold', color='#f0883e')
ax.set_xticks(x)
ax.set_xticklabels(splits, fontsize=10)
ax.set_ylabel('cantidad', fontsize=10)
ax.set_title('failure_anatomy_v1 — split distribution', fontsize=12, pad=8)
ax.legend(loc='upper right', fontsize=9)
ax.set_ylim(0, 135)
ax.grid(axis='y', alpha=0.3)
for sp in ['top','right']:
    ax.spines[sp].set_visible(False)

fig.suptitle('Avance Entrenamiento IA / TensorFlow — ICT SYSTEM', fontsize=16, fontweight='bold', color='#e6edf3', y=0.98)
fig.text(0.5, 0.01, 'commit: c495efc  •  Python 3.11.15 / TensorFlow 2.21.0  •  can_trade=false  •  shadow_mode=true  •  failure_risk_v1 entrenado — estado REVIEW',
         ha='center', fontsize=9, color='#8b949e')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
fig.savefig(OUT + '/neural_training_progress_v1.png', dpi=150, bbox_inches='tight', facecolor='#0f1117')
plt.close(fig)
print('Main chart saved')

# ── LEARNING MAP ───────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 9))
ax.set_xlim(0, 14)
ax.set_ylim(0, 9)
ax.axis('off')
fig.patch.set_facecolor('#0f1117')

def box(x, y, w, h, text, color, text_color='#e6edf3', fontsize=10, bold=True):
    style = 'round,pad=0.15'
    p = FancyBboxPatch((x, y), w, h, boxstyle=style,
                       facecolor=color, edgecolor='#2d3340', linewidth=1.2,
                       alpha=0.95, mutation_aspect=0.4)
    ax.add_patch(p)
    weight = 'bold' if bold else 'normal'
    ax.text(x+w/2, y+h/2, text, ha='center', va='center',
            fontsize=fontsize, color=text_color, weight=weight, wrap=True)
    return (x+w/2, y+h/2)

def arrow(x1, y1, x2, y2, color='#58a6ff'):
    ar = FancyArrowPatch((x1, y1), (x2, y2),
                            arrowstyle='->', mutation_scale=20,
                            color=color, linewidth=1.8)
    ax.add_patch(ar)

ax.text(7, 8.6, 'MAPA DE APRENDIZAJE — ICT SYSTEM IA', ha='center', va='center',
        fontsize=18, fontweight='bold', color='#e6edf3')
ax.text(7, 8.15, 'Evoluci\u00f3n: TensorFlow Outcome v1.001 \u2192 v1.002 \u2192 v1.003 \u2192 Failure Anatomy v1',
        ha='center', va='center', fontsize=11, color='#8b949e')

w, h = 2.6, 0.9
y_base = 6.4

x0 = 0.7; c1 = box(x0, y_base, w, h, 'v1.001\n100 eventos\nCANONICAL_BOS\n6 features\nDense(64)+32+3\nfailure: 0.0000 recall\nBLOCKED/REVIEW', '#21262d', '#f85149', 9)
x1 = 3.6; c2 = box(x1, y_base, w, h, 'v1.002\n292 eventos\nCANONICAL+LITE\n6 features\nDense(64)+32+3\nfailure: 0.0769 recall\nREVIEW', '#21262d', '#d29922', 9)
x2 = 6.5; c3 = box(x2, y_base, w, h, 'v1.003\n292 eventos\n+ features ricas\nBatchNorm+96+48+3\nfailure: 0.2308 recall\nREVIEW', '#21262d', '#58a6ff', 9)
x3 = 9.4; c4 = box(x3, y_base, w, h, 'failure_anatomy_v1\nDataset materializado\n120/96/76 splits\n25/19/26 failure\nREADY_FOR_TRAINING', '#21262d', '#3fb950', 9)
x4 = 12.0; c5 = box(x4, y_base, w, h, 'failure_risk_v1\nPENDIENTE\nModelo binario\nSigmoid output\nPor entrenar', '#2d1f1f', '#f0883e', 9)

arrow(c1[0]+w/2, c1[1]-h/2, c2[0]-w/2, c2[1]-h/2, '#d29922')
arrow(c2[0]+w/2, c2[1]-h/2, c3[0]-w/2, c3[1]-h/2, '#58a6ff')
arrow(c3[0]+w/2, c3[1]-h/2, c4[0]-w/2, c4[1]-h/2, '#3fb950')
arrow(c4[0]+w/2, c4[1]-h/2, c5[0]-w/2, c5[1]-h/2, '#f0883e')

y_fusion = 4.2
ax.text(7, y_fusion+0.5, 'Futura Fus\u00eda Tard\u00eda (Late Fusion)', ha='center', va='center',
        fontsize=12, fontweight='bold', color='#8b949e')
box(5.5, y_fusion-h/2, 3.2, h, 'outcome_probs\nv1.003', '#1a2a3a', '#58a6ff', 9)
box(9.0, y_fusion-h/2, 3.2, h, '+ failure_risk_v1\n\u2192 meta_calibrator\n_shadow', '#2d1f1f', '#f0883e', 9)
arrow(7.1, y_fusion, 9.0, y_fusion, '#8b949e')

y_pol = 2.4
ax.text(7, y_pol+0.4, 'Pol\u00edticas Vigentes', ha='center', va='center',
        fontsize=12, fontweight='bold', color='#8b949e')
box(1.0, y_pol-h/2, 3.8, h, 'can_trade = false\nshadow_mode = true\nentry_authorized = false', '#1a2a1a', '#3fb950', 9)
box(5.2, y_pol-h/2, 3.8, h, 'NO trading\nNO DEMO\nNO live signal\nNO producci\u00f3n', '#2d1f1f', '#f85149', 9)
box(9.4, y_pol-h/2, 3.6, h, 'HOLDOUT solo para\nevaluaci\u00f3n final\nSin OOS tuning', '#21262d', '#d29922', 9)

ax.text(7, 1.2, 'Los datos no autorizan trading.\nEl aprendizaje es diagn\u00f3stico de laboratorio.',
        ha='center', va='center', fontsize=10, color='#8b949e', style='italic')

fig.savefig(OUT + '/neural_learning_map_v1.png', dpi=150, bbox_inches='tight', facecolor='#0f1117')
plt.close(fig)
print('Learning map saved')
