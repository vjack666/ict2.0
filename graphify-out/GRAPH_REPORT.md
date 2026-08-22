# Graph Report - .  (2026-08-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2728 nodes · 6718 edges · 169 communities (113 shown, 56 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 436 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7e69a0c7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- score_fusion.py
- sequence.py
- drift.py
- build_daily_motor_snapshot
- audit_stack.py
- ModelRegistry
- __init__.py
- CheckpointStore
- DatasetSnapshotError
- plan_driver.py
- adapter.py
- SeqConfig
- calibration.py
- mtf_seq_funnel.py
- htf_narrative.py
- detect_market_structure
- agent
- NavigatorConfig
- SessionRef
- evaluate_abstention
- _swing_points
- ToolEvent
- AdaptiveHierarchicalFunnel
- bias_from_tools.py
- brief_lunes.py
- MissionController
- MarketObject
- po3.py
- resolve_outcome
- __init__.py
- mtf_navigation.py
- label_human.py
- filter_bos_thesis
- liquidity_internal_external.py
- exp_agentA_runner.py
- HtfPdIndex
- build_features
- LayerSnapshot
- exp_B3_runner.py
- CertifiedArtifactError
- block_builder.py
- killzone.py
- AnalysisResult
- detect_fvg
- exp_B2_runner.py
- harness_c_falsification.py
- BosConfig
- exp_B4_runner.py
- exp_B5_runner.py
- AgentOrchestrator
- MTFNavigator
- ObjectType
- OutcomeConfig
- turtle_soup.py
- WyckoffAgent
- Expediente
- test_phase_d_lineage.py
- SwingTool
- ICTAgent
- gen_choch_dataset.py
- dealing_range_eq.py
- volume_confirm
- _util.py
- AgentRegistryResolver
- __init__.py
- learning_pipeline.py
- CHOCHTool
- plot_tradingview_zones.py
- detect_liquidity
- ltf_canonical_feed.py
- test_market_object_pd_contract.py
- StructureAgent
- .analyze_bar
- detect_order_blocks
- silver_bullet.py
- MissionStore
- detect_order_blocks_htf
- trade_mgmt.py
- poi_anchor.py
- exp_seq_x_context_state.py
- exp_sequence_x_context_state.py
- BOSTool
- MultiTFContext
- MarketStructure
- label_bos_outcome
- b4_nature_head.py
- scan_classify.py
- test_ai_learning_training_pipeline.py
- load_frames
- reconcile_current_experiments.py
- b1_label_audit.py
- morning_read.py
- train_choch_score.py
- dealing_range.py
- .complete_mission
- b0_baseline_measure.py
- update_mt5_ict.py
- b0_baseline_measure.py
- b1_label_audit_real.py
- opening_readiness.py
- plot_htf_reading.py
- smoke_motor.py
- benchmark.py
- b3_walkforward.py
- gaps.py
- import_forex_data.py
- detect_choch
- signal.py
- architecture_guard.py
- user_data.sh
- start_hermes.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- __init__.py
- acquire_eurusd_20y.sh
- launch_ec2.sh
- b1_label_audit.py
- b2_dataset_factory.py
- b3_walkforward.py
- b4_nature_head.py
- brief_lunes.py
- diag_nav_baseline.py
- diag_nav_baseline_csv.py
- eval_choch_model.py
- eval_model_small.py
- exp_sequence_x_context_state.py
- gen_bos_dataset.py
- gen_choch_dataset.py
- gen_swing_dataset.py
- grok_mtf_batches.py
- grok_run_funnel_20y_full.py
- _htf_check.py
- import_forex_data.py
- b4_make_npz.py
- b4_nature_eval.py
- label_human.py
- learning_pipeline.py
- make_bos_chart.py
- plot_htf_reading.py
- plot_tradingview_zones.py
- probe_choch_nature.py
- regression_nav_strict.py
- scan_classify.py
- smoke_consensus.py
- smoke_motor.py
- smoke_motor_lectura.py
- tna_20y_parallel.py
- tna_audit_runner.py
- tna_fullish_runner.py
- tna_sandbox_runner.py
- train_block_encoder.py
- train_choch_full.py
- train_choch_score.py
- train_nature_head.py
- update_mt5_ict.py
- verify_engine.py
- __init__.py

## God Nodes (most connected - your core abstractions)
1. `MarketObject` - 69 edges
2. `DatasetSnapshotError` - 55 edges
3. `SeqConfig` - 52 edges
4. `run_sequential()` - 51 edges
5. `MTFNavigator` - 44 edges
6. `ModelRegistry` - 44 edges
7. `build_features()` - 42 edges
8. `CheckpointStore` - 39 edges
9. `ModelRegistryError` - 37 edges
10. `resolve_outcome()` - 35 edges

## Surprising Connections (you probably didn't know these)
- `AgentOrchestrator` --uses--> `ICTAgent`  [INFERRED]
  orchestration/orchestrator.py → analysis/ict_agent.py
- `run()` --indirect_call--> `ICTAgent`  [INFERRED]
  scripts/smoke/smoke_motor.py → analysis/ict_agent.py
- `AgentOrchestrator` --uses--> `StructureAgent`  [INFERRED]
  orchestration/orchestrator.py → analysis/structure_agent.py
- `AgentOrchestrator` --uses--> `WyckoffAgent`  [INFERRED]
  orchestration/orchestrator.py → analysis/wyckoff_agent.py
- `ContextConstraints` --uses--> `BosConfig`  [INFERRED]
  engine/mtf_navigation.py → detectors/bos.py

## Import Cycles
- None detected.

## Communities (169 total, 56 thin omitted)

### Community 0 - "score_fusion.py"
Cohesion: 0.07
Nodes (62): BaselineModel, CallableScoreSource, evaluate_offline_oos(), _finite_number(), fit_baseline(), fit_score_fusion(), learn_score_fusion_weights(), _names() (+54 more)

### Community 1 - "sequence.py"
Cohesion: 0.04
Nodes (65): build_rules(), check_invalidation(), InvalidationRule, _opposite_swing_level(), Any, engine/invalidation.py — Invalidacion predefinida y explicita (B3).  Ley 6 (in, Nivel del swing opuesto CONFIRMADO cerrado hasta el sweep (Ley 4)., Evalua las reglas contra la vela i. Devuelve la regla que mata, o None.      S (+57 more)

### Community 2 - "drift.py"
Cohesion: 0.07
Nodes (54): analyze_drift(), build_known_domain(), _canonical_json(), _category(), _category_count(), _coerce_thresholds(), _digest(), _dimension_value() (+46 more)

### Community 3 - "build_daily_motor_snapshot"
Cohesion: 0.07
Nodes (67): _annotation_state(), _asof_time(), build_daily_motor_snapshot(), _canonical_zone_state(), _closed_time(), _coerce_market_object(), _context_state_payload(), DailyMotorConfig (+59 more)

### Community 4 - "audit_stack.py"
Cohesion: 0.08
Nodes (58): a0_data(), a1_schema(), a2_point_in_time(), a3_semantics(), a4_metamorphic(), a5_cross_tf(), a6_lineage(), a7_funnel() (+50 more)

### Community 5 - "ModelRegistry"
Cohesion: 0.09
Nodes (52): _assert_registry_destination(), _canonical_json(), _checkpoint_from_dict(), CheckpointRecord, _contains_parts(), DuplicateCheckpointError, DuplicateModelError, _json_safe() (+44 more)

### Community 6 - "__init__.py"
Cohesion: 0.08
Nodes (46): DatasetSnapshot, Registro inmutable de un snapshot local y su lineage certificado., Infraestructura read-only para consumir resultados certificados del lab., ModelCompatibilityError, ModelRecord, Features/labels no son compatibles con el snapshot registrado., _build_split(), _canonical_json() (+38 more)

### Community 7 - "CheckpointStore"
Cohesion: 0.08
Nodes (49): _assert_safe_destination(), _canonical_json(), Checkpoint, CheckpointExistsError, CheckpointIntegrityError, CheckpointStore, CheckpointStoreError, _contains_parts() (+41 more)

### Community 8 - "DatasetSnapshotError"
Cohesion: 0.11
Nodes (53): CertifiedExperimentManifest, Representación inmutable de un resultado certificado., _as_manifest(), _assert_manifest_references_source(), _assert_writable_snapshot_destination(), _build_schema(), _canonical_json(), CertifiedDatasetReader (+45 more)

### Community 9 - "plan_driver.py"
Cohesion: 0.08
Nodes (50): attach_alignment(), _confirm_objs(), ict_backtest/plan_attach.py — Brecha A1: loop driver nivel 2 (modo OBSERVE)., Adjunta AlignmentReport a la senal. Devuelve la senal con signal['alignment']., _zone_ok_for_m15(), AlignmentReport, build_confirm_from_tf(), _confirm() (+42 more)

### Community 10 - "adapter.py"
Cohesion: 0.09
Nodes (48): build_wyckoff_snapshot(), _context_direction(), _layer_snapshot(), _prefix(), Any, DataFrame, Adaptador read-only de Wyckoff al snapshot ICT/MTF/LTF., Construye un snapshot Wyckoff closed-only y subordinado a ICT. (+40 more)

### Community 11 - "SeqConfig"
Cohesion: 0.08
Nodes (44): Run sequential engine on sequence_tf; index max depth visible at each bar., _avg_range(), _build_eq_pools(), _causal_swings(), Any, ndarray, Motor de eventos secuenciales ICT (no co-ocurrencia de flags).  Cadena canónic, Pivots confirmados solo con velas a la derecha ya cerradas (sin center). (+36 more)

### Community 12 - "calibration.py"
Cohesion: 0.10
Nodes (42): _allowed_indices(), _Block, brier_score(), calibrate_scores(), calibration_error(), CalibrationError, confidence_score(), coverage() (+34 more)

### Community 13 - "mtf_seq_funnel.py"
Cohesion: 0.09
Nodes (31): _count_extra_stages(), funnel_fvg_ob(), funnel_mtf_navigation(), funnel_sequence(), _load_tf(), main(), DataFrame, Funnel de auditoría: FVG/OB + secuencia + navegación MTF (Context State).  Ext (+23 more)

### Community 14 - "htf_narrative.py"
Cohesion: 0.08
Nodes (35): Bias, bias_from_tools_htf(), Sesgo HTF unificado usando las herramientas corregidas de tools/.      Equival, engine.bias — CAPA 1 del motor ICT: Narrativa HTF (SPEC §1).  Lo primero que h, _bias_for_frame(), _compose_htf_bias(), compute_htf_bias(), compute_htf_bias_series() (+27 more)

### Community 15 - "detect_market_structure"
Cohesion: 0.10
Nodes (37): _avg_candle_range(), detect_displacement(), DataFrame, Series, Rango promedio de la vela = media móvil de (high - low).      MATEMÁTICA PURA, _label_swings(), Series, Etiqueta HH/HL/LH/LL por swing confirmado (versión humana). (+29 more)

### Community 16 - "agent"
Cohesion: 0.07
Nodes (39): agent, architect, auditor, conductor, discoverer, documenter, gentle-orchestrator, implementer (+31 more)

### Community 17 - "NavigatorConfig"
Cohesion: 0.11
Nodes (35): audit_object_excursions(), audit_snapshots(), _percentile(), _pip_size_for_object(), Any, Audit AHF temporal navigation plus descriptive FVG/OB magnitude.  This is not, Audit AHF run_timeline()/serialized snapshots plus optional FVG/OB metrics., Measure FVG/OB size and future-only excursion in pips.      Object schema requ (+27 more)

### Community 18 - "SessionRef"
Cohesion: 0.12
Nodes (16): AgentDescriptor, Provider-neutral description of a configured OpenCode agent., AdapterCapabilityError, DelegationRef, OpenCodeCliAdapter, OpenCodeHttpAdapter, _ProcessRecord, ProviderEvent (+8 more)

### Community 19 - "evaluate_abstention"
Cohesion: 0.11
Nodes (32): AbstentionPolicy, AbstentionResult, _canonical_json(), _confidence(), DecisionState, evaluate_abstention(), _fail_closed_result(), _features() (+24 more)

### Community 20 - "_swing_points"
Cohesion: 0.08
Nodes (35): Swing high/low SIN look-ahead, versión humana.      Confirmación por rotura/re, _swing_points(), _closed_df_at_time(), fine_execution(), _lvl(), Any, DataFrame, Series (+27 more)

### Community 21 - "ToolEvent"
Cohesion: 0.10
Nodes (24): ABC, DataFrame, Path, Base de herramienta ICT individual (Fase 1).  Toda herramienta envuelve un det, Contrato de herramienta ICT individual (aislada, vela a vela)., Llama al detector subyacente y devuelve DataFrame enriquecido., Convierte el DataFrame enriquecido en ToolEvents por barra., Append-only: cada evento como línea jsonl con human_score vacío.          El a (+16 more)

### Community 22 - "AdaptiveHierarchicalFunnel"
Cohesion: 0.13
Nodes (21): AdaptiveHierarchicalFunnel, AHFEvent, AHFSnapshot, AHFState, AHFTransition, _ctx_blob(), Any, Enum (+13 more)

### Community 23 - "bias_from_tools.py"
Cohesion: 0.11
Nodes (29): annotate_with_tools(), bias_from_tools(), Any, DataFrame, engine/bias_from_tools.py — Adaptador: sesgo del motor USANDO tools/ (Fase 1 + T, Sesgo por estructura (igual firma que engine.plan._bias_from_frame)     sobre d, Devuelve df anotado compatible con engine.plan (_bias_from_frame) pero     usan, main() (+21 more)

### Community 24 - "brief_lunes.py"
Cohesion: 0.12
Nodes (31): assert_daily_engine_safe(), EngineRegistryError, load_engine_registry(), Any, Path, ValueError, Version and authority boundary between daily runtime and laboratory.  The regi, Raised when the engine authority contract is invalid. (+23 more)

### Community 25 - "MissionController"
Cohesion: 0.10
Nodes (19): MissionController, _now(), Delegate one persisted task and record the provider reference.          The adap, Reconcile provider status without inventing task evidence., Re-open a durable mission after controller/process restart., Record one completion predicate with explicit evidence., Accept a task result only when it has outputs and evidence., Create auditable missions without executing delegated work. (+11 more)

### Community 26 - "MarketObject"
Cohesion: 0.14
Nodes (23): load_csv(), main(), one_tf(), Funnel real FVG/OB + relación explícita sobre EURUSD H1/H4/D1.  Descarga CSV p, MarketObject, _anchor_bar(), _confirm_bar(), FVGOBRelation (+15 more)

### Community 27 - "po3.py"
Cohesion: 0.10
Nodes (29): _bos_exec(), build_po3_state(), compute_po3_complete(), compute_session_open(), _dir_setup(), evaluate_po3(), _has_htf_bias(), _has_session_range() (+21 more)

### Community 28 - "resolve_outcome"
Cohesion: 0.12
Nodes (28): ndarray, Entry plus structural SL/TP for one directional trade., Structural invalidation level; None when no structural anchor exists.      swe, Path-dependent scan after the entry bar (entry fills at its close).      Retur, resolve_outcome(), structural_stop(), TradeLevels, _long_levels() (+20 more)

### Community 29 - "__init__.py"
Cohesion: 0.11
Nodes (19): Resolve functional routes to agents registered in ``opencode.json``., Provider-neutral mission creation and routing., Mission planning and department routing for ICT 2.0., EngramCliMemorySink, MemorySaveResult, Any, Optional Engram memory sink for durable mission closeouts., Save a concise mission summary without making Engram the source of state. (+11 more)

### Community 30 - "mtf_navigation.py"
Cohesion: 0.14
Nodes (21): DisplacementConfig, _causal_swings(), _dealing_range(), NavQuestion, Enum, ndarray, str, Grafo de navegación multi-timeframe — Context State (no entry).  Implementa la (+13 more)

### Community 31 - "label_human.py"
Cohesion: 0.13
Nodes (23): build_daily_bias(), Cableado PARA USO DIARIO: sesgo HTF jerarquico listo para el motor.      Carga, label_bos_file(), label_file(), main(), P4 — Etiqueta HUMANO SINTETICO (teacher labeling) sobre los 226k eventos.  Obj, Procesa features.jsonl de BOS -> labels_human.jsonl usando score_bos_rubric., Procesa un features.jsonl -> labels_human.jsonl. Devuelve ruta out.     htf_ctx (+15 more)

### Community 32 - "filter_bos_thesis"
Cohesion: 0.14
Nodes (22): _cho_events(), main(), P3 — Probe de NATURALEZA del CHOCH (responde la hipotesis del usuario).  El us, build(), Genera grafico interactivo HTML (Plotly.js via CDN) de EURUSD M5 1 mes con los, _render(), _aggregate_htf_bias(), filter_bos_thesis() (+14 more)

### Community 33 - "liquidity_internal_external.py"
Cohesion: 0.13
Nodes (23): detect_fvg(), detect_fvg_htf(), fvg_for_bos(), DataFrame, Series, engine/fvg_poi.py — FVG como POI anclado a la narrativa HTF (Deuda 3).  CAPA P, FVG anclados a la narrativa HTF (SPEC POI).      Añade `fvg_anchored_htf`: Tru, FVG que ORIGINÓ el BOS: el más cercano ANTERIOR en la dirección del BOS. (+15 more)

### Community 34 - "exp_agentA_runner.py"
Cohesion: 0.15
Nodes (23): Wilson score interval for a binomial proportion., wilson_interval(), build_trade(), compute_metrics(), dataset_record(), hashlib_sha256(), last_confirmed_swing(), load_slice_csv() (+15 more)

### Community 35 - "HtfPdIndex"
Cohesion: 0.13
Nodes (16): _detect_pd_arrays(), HtfPdIndex, HtfPdZone, DataFrame, Series, engine/htf_pd_index.py — Indice temporal de PD Arrays HTF (RESCATE de la capa ba, Indice temporal de PD arrays HTF vigentes por vela del LTF.      Construye UNA, Resuelve el mapa LTF->HTF O(n) por TF HTF (merge asof cerrado).          Devue (+8 more)

### Community 36 - "build_features"
Cohesion: 0.15
Nodes (19): build_features(), _fvg_state(), load_frames(), load_tf(), _ob_dir(), DataFrame, Path, Series (+11 more)

### Community 37 - "LayerSnapshot"
Cohesion: 0.18
Nodes (11): _asof_index(), _eq_pools(), LayerSnapshot, MarketState, NavigationPath, Any, Estado point-in-time de una temporalidad (solo velas cerradas)., Camino recorrido en el grafo (auditoría). (+3 more)

### Community 38 - "exp_B3_runner.py"
Cohesion: 0.13
Nodes (23): measured_projection_tp(), v1 fallback target: sequence-range extreme extended by the range height., build_h4_trend_timeline(), build_trade(), compute_metrics(), h4_trend_at(), last_confirmed_swing(), load_slice_csv() (+15 more)

### Community 39 - "CertifiedArtifactError"
Cohesion: 0.19
Nodes (21): CertifiedArtifactError, load_certified_manifest(), _non_empty_string(), _parse_timestamp(), Any, datetime, Path, ValueError (+13 more)

### Community 40 - "block_builder.py"
Cohesion: 0.13
Nodes (19): _load_nature_head(), main(), B5 — ABLATION LAB (A/B/C) — pipeline científico de aprendizaje.  Ejecuta las 7, _collect_blocks(), main(), P2 — Entrena el ENCODER de bloque de velas (el "ojo" auto-supervisado).  Objet, Recolecta bloques CHOCH de TODO el historico M5 usando el pipeline tools/., _to_arrays() (+11 more)

### Community 41 - "killzone.py"
Cohesion: 0.17
Nodes (20): detect_killzones(), DataFrame, datetime, Killzones — port de LuxAlgo ICT Concepts a Python.  Sesiones (horario del exch, Devuelve (ini_utc, fin_utc) de la sesión para el dia de la vela, vía ZoneInfo., Marca sesiones activas por vela.      broker_tz: ZoneInfo | str (nombre IANA), _session_window_utc(), _et_band_to_utc() (+12 more)

### Community 42 - "AnalysisResult"
Cohesion: 0.13
Nodes (11): Compatibility re-exports for the analysis base layer., Compatibility re-exports for the ICT analysis agent., Compatibility re-exports for the Wyckoff analysis agent., AgentProtocol, AnalysisResult, DataFrame, Protocol, DecisionRecord (+3 more)

### Community 43 - "detect_fvg"
Cohesion: 0.15
Nodes (18): _as_candles(), detect_fvg(), Any, Canonical causal ICT Fair Value Gap detector., Detect 3-candle FVGs using only data through the confirmation candle., Canonical ICT detectors., asof_index(), htf_tp() (+10 more)

### Community 44 - "exp_B2_runner.py"
Cohesion: 0.15
Nodes (20): RuntimeError, build_d1_trend_timeline(), build_trade(), compute_metrics(), d1_trend_at(), last_confirmed_swing(), load_slice_csv(), main() (+12 more)

### Community 45 - "harness_c_falsification.py"
Cohesion: 0.17
Nodes (20): apply_costs_to_r(), build_baseline(), build_trade(), build_treatment(), configs(), last_confirmed_swing(), load_source(), main() (+12 more)

### Community 46 - "BosConfig"
Cohesion: 0.17
Nodes (15): BosConfig, _compute_atr(), detect_bos(), _label_swings(), DataFrame, Series, Causal pivots: a bar j is a swing only once lookback bars to its RIGHT have clos, _swing_points() (+7 more)

### Community 47 - "exp_B4_runner.py"
Cohesion: 0.16
Nodes (19): build_trade(), build_trend_timeline(), compute_metrics(), last_confirmed_swing(), load_slice_csv(), main(), paired_delta_bootstrap(), passes_filter() (+11 more)

### Community 48 - "exp_B5_runner.py"
Cohesion: 0.16
Nodes (19): build_trade(), build_trend_timeline(), compute_metrics(), last_confirmed_swing(), load_slice_csv(), main(), paired_delta_bootstrap(), passes_b5_filter() (+11 more)

### Community 49 - "AgentOrchestrator"
Cohesion: 0.18
Nodes (12): Compatibility re-exports for the decision agent layer., Compatibility re-exports for the orchestration layer., DecisionAgent, DecisionConfig, AgentOrchestrator, Coordinate the ICT, Wyckoff, structure, and decision agents., Coordinate per-bar analysis across all trading agents., main() (+4 more)

### Community 50 - "MTFNavigator"
Cohesion: 0.16
Nodes (13): DataFrame, MTFNavigator, Grafo de navegación Context State.      Parameters     ----------     frames, load_tf(), main(), DataFrame, _ohlc(), DataFrame (+5 more)

### Community 51 - "ObjectType"
Cohesion: 0.22
Nodes (10): _Candle, _Candle, Canonical ICT Order Block detector., ObjectState, ObjectType, Enum, str, Objeto de mercado ICT (fuente canónica del motor).  Un MarketObject representa (+2 more)

### Community 52 - "OutcomeConfig"
Cohesion: 0.17
Nodes (17): bootstrap_clustered(), OutcomeConfig, Outcome geometry for sequential-chain experiments (R-multiples).  Pure bar-by-, Cluster bootstrap CIs for mean R and win-rate over closed trades.      Resampl, break_dir_series(), build_anchors(), htf_context(), main() (+9 more)

### Community 53 - "turtle_soup.py"
Cohesion: 0.17
Nodes (18): _coerce_ts(), flag_turtle_soup(), _has_reversal(), is_turtle_soup(), _prev_day_ohlc(), Any, DataFrame, Series (+10 more)

### Community 54 - "WyckoffAgent"
Cohesion: 0.39
Nodes (3): Any, DataFrame, WyckoffAgent

### Community 55 - "Expediente"
Cohesion: 0.14
Nodes (10): Expediente, PhaseEvent, Any, engine/expediente.py — Expediente por señal (Ley 8 / Ley 7 / Ley 4).  Cada señ, Crea un expediente en su nacimiento (al confirmarse el sweep)., Registra un hecho ya decidido. Índice monótono no decreciente., Marca la señal como invalidada por su regla predefinida., Reconstruye un Expediente desde su to_dict (round-trip persistence). (+2 more)

### Community 56 - "test_phase_d_lineage.py"
Cohesion: 0.24
Nodes (15): CausalLink, link(), Any, engine/lineage.py — Consumidor puro de trazabilidad causal (SDD_M2_LINEAGE)., Audita el linaje causal de una señal del motor., trace_setup_lineage(), validate_links(), obj() (+7 more)

### Community 57 - "SwingTool"
Cohesion: 0.18
Nodes (11): main(), _process(), Genera datasets de SWING por TF (M5/H4/D1) para el sistema de aprendizaje.  Fa, _label_swings(), DataFrame, Series, Herramienta SWING (individual, Fase 1) — objeto geométrico PERSISTENTE.  Envue, Pivots clásicos por ventana central. Solo la vela pivot lleva valor     (NaN en (+3 more)

### Community 58 - "ICTAgent"
Cohesion: 0.26
Nodes (5): ICTAgent, Any, DataFrame, Series, Read feature columns already present; do not invent structure.

### Community 59 - "gen_choch_dataset.py"
Cohesion: 0.25
Nodes (14): _classify_trend(), _compute_atr(), detect_trend(), DataFrame, Series, _slope_of_last_two(), _swing_high_low(), TrendConfig (+6 more)

### Community 60 - "dealing_range_eq.py"
Cohesion: 0.16
Nodes (12): classify_zone(), compute_zone_class(), DealingRangeInput, _eq(), _is_close_to(), ict_backtest/dealing_range.py — Brecha C: dealing range premium/discount (Fase 5, Swing HTF cerrado antes de ``at_time``.      Anti look-ahead: solo velas con `, Clasifica la zona segun el dealing range del swing HTF.      Usa el midpoint d (+4 more)

### Community 61 - "volume_confirm"
Cohesion: 0.18
Nodes (15): _bias_direction(), detect_liquidity_htf(), nearest_liquidity_target(), DataFrame, Series, engine/liquidity_levels.py — Liquidez BSL/SSL anclada al sesgo HTF (Deuda 4)., Ratio de volumen en las velas que BARREN el BSL/SSL previo (no gate).      Tod, Devuelve el objetivo de liquidez más cercano al último close.      {'side': 'B (+7 more)

### Community 62 - "_util.py"
Cohesion: 0.15
Nodes (16): avg_candle_range(), closed_merge_asof(), closed_row_at_time(), infer_tf_duration(), Any, DataFrame, Series, engine/_util.py — helpers compartidos del MOTOR (permanente).  Migrado desde i (+8 more)

### Community 63 - "AgentRegistryResolver"
Cohesion: 0.16
Nodes (8): AgentRegistryResolver, Path, Read-only resolver for the local OpenCode agent registry., Path, test_all_route_agent_keys_are_registered_in_opencode(), test_http_adapter_creates_delegates_and_polls_provider_status(), test_opencode_adapter_builds_contractual_dry_run_without_launching_process(), test_opencode_adapter_rejects_prompt_without_mission_contract()

### Community 64 - "__init__.py"
Cohesion: 0.23
Nodes (12): detect_fvg(), DataFrame, Series, _track_fvg_fill(), detect_order_blocks(), DataFrame, Series, _track_ob_validity() (+4 more)

### Community 65 - "learning_pipeline.py"
Cohesion: 0.25
Nodes (14): block0_baseline(), cmd_explain(), cmd_pause(), cmd_resume(), cmd_run(), cmd_status(), cmd_why(), _ensure() (+6 more)

### Community 66 - "CHOCHTool"
Cohesion: 0.18
Nodes (8): main(), _nature_targets(), NatureHead, P5 — HEAD B: modelo que aprende la NATURALEZA del CHOCH (recomendacion auditoria, Re-mide la naturaleza P3 (confirm vs reclaim) y devuelve (bars, cds, labels)., CHOCHTool, DataFrame, Herramienta CHOCH (individual, Fase 1) — CORREGIDA segun tesis 02_MSS_CHOCH.

### Community 67 - "plot_tradingview_zones.py"
Cohesion: 0.21
Nodes (15): _format_price(), _label_positions(), _load(), main(), _plot(), DataFrame, Path, Series (+7 more)

### Community 68 - "detect_liquidity"
Cohesion: 0.19
Nodes (13): build_liquidity_context(), canonical_sweep(), DataFrame, detectors/liquidity_context.py — Fuente UNICA de liquidez y sweep (R3, libro 05), Sweep de liquidez canonico (libro 05 §0 #3). Rompe y cierra adentro.      Defi, Fuente unica de contexto de liquidez para mapa + senal.      - sweep canonico, detect_liquidity(), DataFrame (+5 more)

### Community 69 - "ltf_canonical_feed.py"
Cohesion: 0.29
Nodes (13): _asof_prefix(), build_ltf_canonical_feed(), Any, DataFrame, Adaptador read-only de objetos canónicos para la lectura LTF.  Este módulo no, Aplica observación causal de touch sobre una copia lógica del objeto., Construye la entrada canónica read-only del motor diario.      ``frames`` pued, _sequence_summary() (+5 more)

### Community 70 - "test_market_object_pd_contract.py"
Cohesion: 0.26
Nodes (14): _base(), test_all_pd_array_types_are_canonical(), test_created_can_invalidate_or_expire_without_becoming_tradable(), test_first_touch_cannot_precede_tradable_bar(), test_first_touch_requires_positive_touch_count(), test_foundational_direction_zone_and_score_invariants(), test_invalidated_bar_cannot_precede_candidate(), test_lifecycle_transition_contract() (+6 more)

### Community 71 - "StructureAgent"
Cohesion: 0.25
Nodes (5): Compatibility re-exports for the structure analysis agent., Any, DataFrame, Series, StructureAgent

### Community 72 - ".analyze_bar"
Cohesion: 0.18
Nodes (9): Any, DataFrame, ndarray, Append orchestrated agent columns for each row in the context., Return the decision confidence for the requested bar index., Return the decision bias for the requested bar index., Convert detected event dictionaries into a compact CSV-like string., Analyze a single bar and return the orchestrated feature payload. (+1 more)

### Community 73 - "detect_order_blocks"
Cohesion: 0.31
Nodes (12): _as_candles(), detect_order_blocks(), Any, Detect OB only after the opposite footprint candle has a closed follow-through., c(), test_bearish_fvg(), test_bearish_ob_requires_closed_followthrough(), test_bullish_fvg_confirmed_at_third_close() (+4 more)

### Community 74 - "silver_bullet.py"
Cohesion: 0.24
Nodes (12): flag_silver_bullet(), is_silver_bullet(), Any, DataFrame, datetime, engine/silver_bullet.py — Silver Bullet (C2, PERMANENTE).  Rescatado de ict_ba, Anota sb_confirmed / sb_killzone en cada senal (atributos dinamicos).      No, Normaliza un timestamp (datetime / string) a datetime tz-aware UTC. (+4 more)

### Community 75 - "MissionStore"
Cohesion: 0.28
Nodes (6): MissionStore, _now(), Any, Path, Persist mission state under a caller-provided directory.      Tests and previews, Return durable mission IDs in deterministic order.

### Community 76 - "detect_order_blocks_htf"
Cohesion: 0.29
Nodes (11): detect_order_blocks(), detect_order_blocks_htf(), order_block_for_bos(), DataFrame, Series, engine/order_block.py — Order Block anclado a la narrativa HTF (Deuda 2).  CAP, Order Blocks anclados a la narrativa HTF (SPEC POI).      Añade `ob_anchored_h, OB que ORIGINÓ el BOS: el más cercano ANTERIOR en la dirección del BOS.      A (+3 more)

### Community 77 - "trade_mgmt.py"
Cohesion: 0.29
Nodes (11): apply_trade_management(), _check_direction(), _exit_dict(), partial_exit(), engine/trade_mgmt.py — E1 Trade Management (PERMANENTE).  Rescatado de ict_bac, Mueve SL a Break-Even (=entry) si el precio avanzo >= be_trigger_r * risk., True si el precio toco tp1 (liquidez internal) y corresponde cerrar pct., SL deslizante que solo mejora (sube en long / baja en short), nunca empeora. (+3 more)

### Community 78 - "poi_anchor.py"
Cohesion: 0.27
Nodes (9): build_htf_structure_index(), make_htf_poi_fn(), _ParentEvent, poi_present(), DataFrame, engine/poi_anchor.py — Ancla narrativa de POI al TF padre (Brecha B, tesis 18)., True si en los TF padre hay BOS/CHOCH en la MISMA direccion que `target`., Lista plana de eventos BOS/CHOCH en los TF padre, ordenada por time.      Cada (+1 more)

### Community 79 - "exp_seq_x_context_state.py"
Cohesion: 0.27
Nodes (10): chi2_and_cramers(), context_bucket(), h1_alignment(), main(), measure_outcome(), ndarray, EXP SEQUENCE x CONTEXT STATE — event-anchored, point-in-time, local.  Diseno a, Favor/Neutral/Contra agregado (conservamos las 3 individuales tambien). (+2 more)

### Community 80 - "exp_sequence_x_context_state.py"
Cohesion: 0.31
Nodes (10): _agg(), _bucket(), _extract_location(), _load(), _location_favorable(), main(), _outcomes(), Any (+2 more)

### Community 81 - "BOSTool"
Cohesion: 0.27
Nodes (7): _commit(), main(), _process(), B2 — DATASET FACTORY MULTI-PAR (pipeline científico).  Generaliza la generacio, _sha(), BOSTool, DataFrame

### Community 82 - "MultiTFContext"
Cohesion: 0.27
Nodes (9): dict, build_multitf_context(), extract_htf_layer(), MultiTFContext, Any, Fase 1 — MultiTFContext: infraestructura de lectura multitemporal.  Objetivo ú, Dict {tf: snapshot_closed_only} para todos los TF de la cadena.      Es un dic, Construye el MultiTFContext closed-only en t.      Delega en build_context_sta (+1 more)

### Community 83 - "MarketStructure"
Cohesion: 0.20
Nodes (6): MarketStructure, Direccion del ultimo BOS emitido (1 alcista, -1 bajista, 0 sin BOS)., Nivel del ultimo BOS emitido (NaN si no hubo)., Direccion del ultimo CHoCH emitido (1/-1/0)., Conteos de estado por vela (diagnostico rapido)., Resultado de la deteccion: frame anotado + vista de estado.      `frame` conti

### Community 84 - "label_bos_outcome"
Cohesion: 0.27
Nodes (9): confirm_score(), label_bos_outcome(), label_choch_outcome(), DataFrame, Series, engine/labels.py — ETIQUETADO DE RESULTADO (MIRA EL FUTURO).  ================, Score de confirmación posterior (0/1) para el BOS en el índice `i`.      Mira, Etiqueta el desenlace (hit / motivo de descarte) de cada BOS emitido.      Mir (+1 more)

### Community 85 - "b4_nature_head.py"
Cohesion: 0.29
Nodes (7): _folds(), main(), _nature_blocks(), NatureHead, _pr_auc(), B4 — NATURE HEAD + BASELINES (pipeline científico, BLOQUE 4).  Entrena natural, Re-mide naturaleza P3 y devuelve (X_flat, y, years) por CHOCH real.

### Community 86 - "scan_classify.py"
Cohesion: 0.22
Nodes (3): detect_defects(), is_orphan(), Escáner de clasificación ORIENTADO A DEFICIENCIAS (ICT SYSTEM).  No es una tax

### Community 87 - "test_ai_learning_training_pipeline.py"
Cohesion: 0.40
Nodes (9): _manifest(), _pipeline(), _snapshot(), test_equal_timestamps_cannot_cross_a_partition_boundary(), test_pipeline_is_deterministic_and_checkpoint_state_is_a_skeleton(), test_raw_or_non_certified_dataset_is_rejected(), test_registry_configuration_and_seed_must_match_pipeline(), test_resume_reloads_only_the_matching_checkpoint() (+1 more)

### Community 88 - "load_frames"
Cohesion: 0.36
Nodes (7): load_frames(), load_tf(), DataFrame, Path, engine/data_feed.py — Carga de velas para el MOTOR (permanente).  Lee los parq, Carga un TF crudo. Devuelve df con columnas time/open/high/low/close., Carga varios TF. Devuelve {tf: df}. Sin features del backtest.

### Community 89 - "reconcile_current_experiments.py"
Cohesion: 0.50
Nodes (7): build_reconciliation(), main(), _markdown(), Any, Reconcile the current A/B/C experiment batch from audit JSON files.  This scri, _read_audit(), _status()

### Community 90 - "b1_label_audit.py"
Cohesion: 0.36
Nodes (7): _label_ep_stats(), _load(), main(), _nature_stats(), B1 — AUDITORÍA DE DATASET Y LABEL (pipeline científico).  Audita label_ep y na, Replica label_ep de gen_choch_dataset y mide positividad/estabilidad., Replica nature P3 (probe) y mide balance/reclaim.

### Community 91 - "morning_read.py"
Cohesion: 0.38
Nodes (6): gen_charts(), main(), Orquestador de lectura visual matutina ICT SYSTEM (EURUSD).  Best-effort: inte, Refresco best-effort de la punta MT5. Devuelve True si OK, False si no., Genera los charts para cada simbolo. Devuelve lista de simbolos fallidos., run_mt5()

### Community 92 - "train_choch_score.py"
Cohesion: 0.43
Nodes (6): cv_auc(), load(), main(), make_models(), DataFrame, Entrena modelo IA para calibrar score CHOCH (F4/F5).  Lee data/learning/choch/

### Community 93 - "dealing_range.py"
Cohesion: 0.53
Nodes (5): compute_dealing_range(), dealing_range_htf(), DealingRangeConfig, _is_favorable(), Premium/Discount EQ50%. SIN indicadores, SIN OTE/Fibonacci (ICT_RULEBOOK §9).

### Community 94 - ".complete_mission"
Cohesion: 0.47
Nodes (3): Path, Close only when every SDD completion predicate is true., Write a human-readable durable closeout/checkpoint worklog.

### Community 95 - "b0_baseline_measure.py"
Cohesion: 0.53
Nodes (5): _git_commit(), main(), B0 baseline measurement — REAL, not hardcoded.  Replica EXACTAMENTE el entrena, _sha256(), _train()

### Community 96 - "update_mt5_ict.py"
Cohesion: 0.47
Nodes (5): download_tip(), main(), merge_tip(), Path, ACTUALIZADOR MT5 -> ICT SYSTEM (reusa el terminal MT5 de SMC-SYSTEMS).  Estrat

### Community 97 - "b0_baseline_measure.py"
Cohesion: 0.53
Nodes (5): _git_commit(), main(), B0 baseline measurement — REAL, not hardcoded.  Replica EXACTAMENTE el entrena, _sha256(), _train()

### Community 98 - "b1_label_audit_real.py"
Cohesion: 0.47
Nodes (5): _leakage_check(), main(), B1 — AUDITORÍA REAL de label_ep / label_peak / label_dir sobre el dataset CHOCH., Point-in-time: el label de la fila k solo usa close desde break_bar+1 en adelant, _stability()

### Community 99 - "opening_readiness.py"
Cohesion: 0.53
Nodes (4): check(), Read-only readiness check for the next market opening.  This command never conne, run(), test_readiness_check_is_fail_closed()

### Community 100 - "plot_htf_reading.py"
Cohesion: 0.53
Nodes (5): bias_color(), load(), main(), plot_tf(), Grafico de lectura HTF (D1/H4/H1) sobre datos reales EURUSD.  Objetivo: mostra

### Community 101 - "smoke_motor.py"
Cohesion: 0.47
Nodes (5): make_ohlc(), DataFrame, FASE 2b — primer arranque real del motor dentro de ICT SYSTEM.  Objetivo: hace, run(), step()

### Community 102 - "benchmark.py"
Cohesion: 0.60
Nodes (4): _host_tag(), main(), benchmark.py — Linea base ict2.0 (tu PC) para comparar con EC2.  Mide, por evi, _run()

### Community 103 - "b3_walkforward.py"
Cohesion: 0.60
Nodes (4): _folds(), _load(), main(), B3 — WALK-FORWARD REAL (pipeline científico).  Elimina train_test_split aleato

### Community 104 - "gaps.py"
Cohesion: 0.50
Nodes (3): detect_nwog_ndog(), DataFrame, NWOG / NDOG — port de LuxAlgo ICT Concepts a Python.  NWOG (New Week Opening G

## Knowledge Gaps
- **17 isolated node(s):** `ICTSignal`, `$schema`, `enabled`, `type`, `url` (+12 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **56 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `build_features()` connect `build_features` to `__init__.py`, `build_daily_motor_snapshot`, `detect_liquidity`, `plot_htf_reading.py`, `exp_B3_runner.py`, `plot_tradingview_zones.py`, `smoke_motor.py`, `exp_B2_runner.py`, `detect_market_structure`, `exp_B4_runner.py`, `exp_B5_runner.py`, `OutcomeConfig`, `brief_lunes.py`, `dealing_range.py`, `_util.py`?**
  _High betweenness centrality (0.075) - this node is a cross-community bridge._
- **Why does `MarketObject` connect `MarketObject` to `sequence.py`, `build_daily_motor_snapshot`, `ltf_canonical_feed.py`, `test_market_object_pd_contract.py`, `detect_order_blocks`, `plan_driver.py`, `detect_fvg`, `ObjectType`, `test_phase_d_lineage.py`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `detect_market_structure()` connect `detect_market_structure` to `build_daily_motor_snapshot`, `build_features`, `htf_narrative.py`, `poi_anchor.py`, `MarketStructure`, `_swing_points`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `MarketObject` (e.g. with `DailyMotorConfig` and `_Candle`) actually correct?**
  _`MarketObject` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `DatasetSnapshotError` (e.g. with `CertifiedArtifactError` and `CertifiedExperimentManifest`) actually correct?**
  _`DatasetSnapshotError` has 25 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `SeqConfig` (e.g. with `ContextConstraints` and `LayerSnapshot`) actually correct?**
  _`SeqConfig` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `MTFNavigator` (e.g. with `AdaptiveHierarchicalFunnel` and `AHFConfig`) actually correct?**
  _`MTFNavigator` has 11 INFERRED edges - model-reasoned connections that need verification._