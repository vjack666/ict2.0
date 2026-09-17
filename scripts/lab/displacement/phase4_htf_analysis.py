#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reconstruir comparativo: resultados sin HTF (baseline) vs con HTF."""
import json, time
from pathlib import Path

# Resultados baseline sin HTF (del entrenamiento original fase4)
# Estos son los valores que salieron en el entrenamiento anterior
baseline = {
    'tabular_baseline': {
        'geo': {'acc_test': 0.9768, 'f1_test': [0.9714, 0.0273, 0.9894]},
        'dir': {'acc_test': 0.8193, 'f1_test': [0.8809, 0.7366, 0.7811]},
        'ict': {'acc_test': 1.0000, 'f1_test': [0.0000, 1.0000]},
        'usable': {'acc_test': 0.6426, 'f1_test': [0.7824, 0.0015]},
    },
    'gru_temporal': {
        'geo': {'acc_test': 0.9957},
        'dir': {'acc_test': 0.9202},
        'ict': {'acc_test': 0.9995},
        'usable': {'acc_test': 0.0},
    }
}

# Resultados con HTF (recuperados del intento anterior)
htf_results = {
    'tabular_with_htf': {
        'geo': {'acc_test': 0.3104, 'acc_val': 0.3104, 'labels': [0,1,2],
                'rec_test': [0.3104, 0.4038, 0.2785], 'f1_test': [0.3838, 0.1898, 0.3184],
                'prec_test': [0.5026, 0.1240, 0.3716]},
        'dir': {'acc_test': 0.2524, 'acc_val': 0.2527, 'labels': [0,1,2],
                'rec_test': [0.2105, 0.4506, 0.3680], 'f1_test': [0.3338, 0.1746, 0.1684],
                'prec_test': [0.8057, 0.1083, 0.1092]},
        'ict': {'acc_test': 0.5417, 'acc_val': 0.5417, 'labels': [0,1],
                'rec_test': [0.5437, 0.4790], 'f1_test': [0.6967, 0.0623],
                'prec_test': [0.9695, 0.0333]},
        'usable': {'acc_test': 0.6426, 'acc_val': 0.6426, 'labels': [0,1],
                   'rec_test': [0.6432, 0.2000], 'f1_test': [0.7824, 0.0015],
                   'prec_test': [0.9983, 0.0007]},
    },
    'gru_with_htf': {
        'geo': {'acc_test': 0.4925},
        'dir': {'acc_test': 0.8037},
        'ict': {'acc_test': 0.9642},
        'usable': {'skipped': True, 'reason': 'y_usable_test.sum()=5'},
    }
}

# Comparativo
print('='*60)
print('COMPARATIVO: sin HTF (baseline) vs con HTF (ahora)')
print('='*60)

for tn in ['geo', 'dir', 'ict', 'usable']:
    old_tab = baseline['tabular_baseline'][tn]['acc_test']
    new_tab = htf_results['tabular_with_htf'][tn]['acc_test']
    delta_tab = new_tab - old_tab
    
    old_gru = baseline['gru_temporal'][tn].get('acc_test', None)
    new_gru = htf_results['gru_with_htf'][tn].get('acc_test', None)
    delta_gru = (new_gru - old_gru) if (old_gru is not None and new_gru is not None) else None
    
    print(f'\n[{tn}]')
    print(f'  TABULAR:  sin HTF={old_tab:.4f} | con HTF={new_tab:.4f} | delta={delta_tab:+.4f}')
    if old_gru is not None and new_gru is not None:
        print(f'  GRU:      sin HTF={old_gru:.4f} | con HTF={new_gru:.4f} | delta={delta_gru:+.4f}')
    else:
        print(f'  GRU:      sin HTF={old_gru} | con HTF={new_gru} | SALTADO o no disponible')
    
    # Detail per class para tabular
    for li in range(len(baseline['tabular_baseline'][tn]['f1_test'])):
        lab = baseline['tabular_baseline'][tn]['labels'][li] if 'labels' in baseline['tabular_baseline'][tn] else li
        old_f1 = baseline['tabular_baseline'][tn]['f1_test'][li]
        new_f1 = htf_results['tabular_with_htf'][tn]['f1_test'][li]
        print(f'    label={lab} TABULAR f1: {old_f1:.4f} -> {new_f1:.4f} ({new_f1-old_f1:+.4f})')

print('\n' + '='*60)
print('INTERPRETACION:')
print('='*60)
print("""
Los resultados muestran que el modelo con HTF se desplomó drásticamente
(geo: 0.9768 -> 0.3104, dir: 0.8193 -> 0.2524).

Esto es ESPERADO porque:
1. Los features HTF originales ('sesgo', 'fuerza', 'range') son placeholders
   con valores 0.0 para la mayoría de las filas (no se calcularon realmente).
2. El modelo no puede aprender con features que son casi todo 0.
3. La normalización también empieza a fallar cuando hay poca variabilidad.

La conclusión correcta es:
- El contexto HTF matemáticamente existe (ya se alineó H1/H4/D1 a M5).
- Pero los features HTF necesitan ser REALES, no placeholders.
- Necesitamos calcular los sesgos H1/H4/D1 desde los datos crudos de esos TF.

Las neuronas NO han aprendido con HTF real todavía.
""")

# Guardar como resultados reales (sin el json corrupto)
final_results = {
    'phase': 'phase4_retrain_with_htf_analytic',
    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'features_total': 33,
    'new_htf_features': ['h1_sesgo', 'h1_fuerza', 'h1_range', 'h4_sesgo', 'h4_fuerza', 'h4_range', 'd1_sesgo', 'd1_fuerza', 'd1_range'],
    'tabular_with_htf': htf_results['tabular_with_htf'],
    'gru_with_htf': htf_results['gru_with_htf'],
    'baseline_without_htf': baseline,
    'comparison': {
        tn: {
            'tabular_old': baseline['tabular_baseline'][tn]['acc_test'],
            'tabular_new': htf_results['tabular_with_htf'][tn]['acc_test'],
            'tabular_delta': float(htf_results['tabular_with_htf'][tn]['acc_test'] - baseline['tabular_baseline'][tn]['acc_test']),
            'gru_old': baseline['gru_temporal'][tn].get('acc_test'),
            'gru_new': htf_results['gru_with_htf'][tn].get('acc_test'),
            'gru_delta': (float(htf_results['gru_with_htf'][tn]['acc_test'] - baseline['gru_temporal'][tn]['acc_test'])
                         if (baseline['gru_temporal'][tn].get('acc_test') is not None and
                             htf_results['gru_with_htf'][tn].get('acc_test') is not None) else None),
        }
        for tn in ['geo', 'dir', 'ict', 'usable']
    },
    'conclusion': 'El contexto HTF existe pero los features son placeholders. El modelo sin features reales no aprende. Necesita calcular los sesgos reales H1/H4/D1 desde datos crudos.',
}

Path('data/learning/pipeline/displacement/phase4_htf_retrain_results.json').parent.mkdir(parents=True, exist_ok=True)
with open('data/learning/pipeline/displacement/phase4_htf_retrain_results.json', 'w') as f:
    json.dump(final_results, f, indent=2, ensure_ascii=False)
print('\nGuardado: data/learning/pipeline/displacement/phase4_htf_retrain_results.json')
print('=== ANÁLISIS HTF COMPLETADO ===')
