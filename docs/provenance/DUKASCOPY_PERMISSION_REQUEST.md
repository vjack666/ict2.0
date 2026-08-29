# Solicitud de autorización — dataset histórico EURUSD

> Plantilla para enviar al proveedor. No es evidencia de autorización y no debe
> cambiar `provenance_status` hasta recibir una respuesta escrita verificable.

## Destinatario

Usar el canal oficial de API para desarrolladores de Dukascopy:

- https://www.dukascopy.com/trading-tools/api/apply
- https://www.dukascopy.com/swiss/docs/api/index.php

## Texto sugerido

**Asunto:** Request for written permission — private automated historical EURUSD research

Hello Dukascopy team,

I am conducting a private, non-commercial research project on causal and
point-in-time detection of market-structure events. I would like written
confirmation that the following use is permitted under the applicable Dukascopy
terms or under a supplementary agreement:

- instrument: EUR/USD spot bid;
- historical range: 2006-01-01 through 2025-12-31;
- timeframes: H1, H4 and D1;
- acquisition: automated local download through the Dukascopy historical-data
  service or an official API (please confirm whether `dukascopy-node` is an
  authorized client; if not, I will use the method you specify);
- storage: private local research storage only;
- use: calculate derived technical event metadata, causal lineage and
  reproducibility hashes;
- distribution: no redistribution of raw quotes or derivative datasets;
- publication: no raw data publication; only aggregated methodological results,
  subject to your attribution and retention requirements;
- commercial use: none, unless separately agreed in writing.

Please confirm explicitly:

1. whether automated acquisition is permitted for this scope;
2. whether the downloaded CSV files may be retained in private local storage;
3. whether derived event labels, hashes and aggregated statistics may be kept;
4. whether a registration, API key, rate limit, attribution or deletion rule
   applies;
5. whether this use is covered by the personal/non-commercial terms or requires
   a supplementary written agreement; and
6. the exact approved endpoint/client and applicable version.

Thank you. Please provide the applicable terms or written authorization so that
I can preserve it with the research provenance record.

## Evidencia que debe conservarse si responden

- mensaje original y respuesta completa, preferiblemente `.eml` o PDF;
- fecha/hora UTC y dominio/canal del remitente;
- URL o contrato citado por el proveedor;
- SHA-256 del archivo de respuesta;
- alcance autorizado, restricciones, expiración y atribución;
- decisión humana documentada sobre si cubre el snapshot existente.

## Protocolo para el log de una adquisición futura autorizada

No ejecutar hasta tener autorización y confirmar el cliente aprobado. La ejecución
debe ocurrir en un checkout limpio y conservar stdout/stderr, parámetros, versión
de Node/npm/cliente, fecha UTC, archivos producidos, hashes y estado Git. La
metadata solo podrá cambiar a `PASS` después de revisar ese paquete y repetir A7.
