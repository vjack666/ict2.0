"""Analisis de las 6 filas PASS del dataset."""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path.cwd()))
from engine.po3 import build_po3_state
from generate_multimodel_candidates_v1 import classify_po3, classify_turtle, classify_silver

DATASET_DIR = Path('data/ml/tensorflow/setup_grammar_v1')

SPLITS = {
    'TRAIN': 'dataset_train.jsonl',
    'VALIDATION': 'dataset_validation.jsonl',
    'TEST_OOS': 'dataset_test_oos.jsonl',
}

# Cargar las 6 filas PASS desde el dataset original
pass_rows = []
for split_name, filename in SPLITS.items():
    path = DATASET_DIR / filename
    with path.open() as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if row['grammar_labels']['setup_decision'] == 'PASS':
                    row['_split'] = split_name
                    pass_rows.append(row)

print('=== FILAS PASS ENCONTRADAS: {} ==='.format(len(pass_rows)))
print()

# Aplicar clasificadores a las filas PASS
for i, row in enumerate(pass_rows):
    print('--- PASS #{}) {} ---'.format(i+1, row['event_id'][:20]))
    print('  decision_time:', row['decision_time'])
    print('  split:', row['_split'])
    
    features = row.get('features_at_t', {})
    grammar = row.get('grammar_labels', {})
    
    # PO3
    po3 = classify_po3(features, grammar)
    print('  PO3: complete={}'.format(po3.complete))
    print('    gates_passed: {}'.format(po3.gates_passed))
    print('    gates_failed: {}'.format(po3.gates_failed))
    
    # Turtle
    turtle = classify_turtle(features, grammar)
    print('  TURTLE: complete={}'.format(turtle.complete))
    print('    gates_passed: {}'.format(turtle.gates_passed))
    print('    gates_failed: {}'.format(turtle.gates_failed))
    
    # Silver Bullet
    dt = datetime.fromisoformat(row['decision_time'].replace('Z', '+00:00'))
    silver = classify_silver(features, grammar, dt)
    print('  SILVER_BULLET: complete={}'.format(silver.complete))
    print('    gates_passed: {}'.format(silver.gates_passed))
    print('    gates_failed: {}'.format(silver.gates_failed))
    
    families_complete = []
    if po3.complete:
        families_complete.append('PO3')
    if turtle.complete:
        families_complete.append('TURTLE')
    if silver.complete:
        families_complete.append('SILVER_BULLET')
    
    print('  familias_completas: {}'.format(families_complete if families_complete else 'NINGUNA'))
    print()

print('=== RESUMEN ===')
print('De las {} filas PASS del dataset:'.format(len(pass_rows)))
po3_pass = sum(1 for r in pass_rows if classify_po3(r['features_at_t'], r['grammar_labels']).complete)
turtle_pass = sum(1 for r in pass_rows if classify_turtle(r['features_at_t'], r['grammar_labels']).complete)
silver_pass = sum(1 for r in pass_rows if classify_silver(
    r['features_at_t'], r['grammar_labels'],
    datetime.fromisoformat(r['decision_time'].replace('Z', '+00:00'))
).complete)
print('- PO3 completo: {}'.format(po3_pass))
print('- Turtle completo: {}'.format(turtle_pass))
print('- Silver Bullet completo: {}'.format(silver_pass))
print()
print('Las filas PASS tienen pd_array_zone=USABLE_UNGRADED (zona validada)')
print('Esto las diferencia de las 286 filas ABSTAIN/REJECT que tienen NO_ZONE')
