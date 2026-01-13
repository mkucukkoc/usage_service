# Usage Service

Usage Service, `pdf-read-fresh` gibi üretici servislerin gönderdiği usage eventlerini toplayan, idempotent şekilde yazan ve Firestore tarafında günlük/aylık agregasyonlar oluşturan bağımsız bir mikroservistir.

## Özellikler

- **Event ingest**: `/v1/usage/events` ile event kabul eder.
- **Dedup (idempotency)**: `requestId` daha önce işlendi ise tekrar yazmaz.
- **Aggregate**: `usage_daily` ve `usage_monthly` koleksiyonlarına agregasyon yazar.
- **Plan snapshot**: Event içindeki plan bilgisini günlük/aylık dokümana taşır.
- **Opsiyonel raw event**: `WRITE_RAW_EVENTS=true` ise `usage_events/{eventId}` olarak ham event yazımı.

## Endpointler

### POST `/v1/usage/events`

Kullanım eventini ingest eder.

**Headers**
- `X-Internal-Key`: `USAGE_SERVICE_INTERNAL_KEY` set edilmişse zorunlu.

**Response**
```json
{
  "ok": true,
  "deduped": false,
  "requestId": "req_123",
  "eventId": "req_123"
}
```

### GET `/health`

Basit sağlık kontrolü.

## Event Şeması (Özet)

`event_builder` ile üretilen payload beklenir. Minimum alanlar:

- `requestId`
- `userId`
- `timestamp` (Unix epoch seconds, UTC)
- `action`

`eventId` opsiyoneldir. `eventId` gelmezse `eventId = requestId` kabul edilir.

`timestamp` değeri UTC normalize edilir ve `YYYYMMDD / YYYYMM` hesaplamaları UTC üzerinden yapılır.

`action` serbest bir string olsa da aşağıdaki değerler önerilir:

- `chat`
- `analyze_pdf`
- `generate_ppt`
- `analyze_image`
- `image_generation`
- `video_generation`

**Örnek payload**
```json
{
  "requestId": "req_123",
  "eventId": "req_123",
  "timestamp": 1768206132,
  "userId": "uid_abc",
  "action": "analyze_pdf",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "inputTokens": 1200,
  "outputTokens": 800,
  "costUSD": 0.0123,
  "costTRY": 0.39,
  "plan": { "tier": "pro", "isPremium": true },
  "metadata": { "pages": 12, "fileType": "pdf" }
}
```

Desteklenen alanlar: `endpoint`, `provider`, `model`, `inputTokens`, `outputTokens`, `cost`, `costUSD`, `plan`, `metadata`, vb.

**Cost alanları**

- `costUSD`: zorunlu.
- `costTRY`: opsiyonel (yoksa servis hesaplayabilir).
- `cost`: deprecated, kullanmayın.

## Firestore Şeması

### `usage_events` (opsiyonel debug)
- Doc ID: `{eventId}`
- TTL (7-30 gün) önerilir

### `usage_daily`
- Doc ID: `{userId}_{YYYYMMDD}` (UTC)
- Alanlar:
  - `totalInputTokens`, `totalOutputTokens`
  - `totalCostTry`, `totalCostUsd`
  - `actions.{action}.tokensIn/out/costTry/costUsd`
  - `lastEventAt`, `planSnapshot`

### `usage_monthly`
- Doc ID: `{userId}_{YYYYMM}` (UTC)
- `usage_daily` ile aynı alanlar

### `request_dedup`
- Doc ID: `{requestId}`
- Idempotency için kullanılır

`request_dedup/{requestId}` varsa servis Firestore’da **hiçbir aggregate update yapmaz** ve `deduped: true` döner. Dedup dokümanı ve aggregate yazımları transaction içinde atomik yürütülür.

Idempotency `requestId` bazındadır; aynı `requestId` ile gelen event’ler farklı `eventId` içerse bile deduped kabul edilir.

`request_dedup`, `usage_daily` ve `usage_monthly` güncellemeleri tek Firestore transaction içinde yapılır; kısmi yazım olmaz.

## Ortam Değişkenleri

- `FIREBASE_SERVICE_ACCOUNT_BASE64`: Firestore servis hesabı (base64 JSON).
- `USAGE_SERVICE_INTERNAL_KEY`: İç erişim anahtarı (opsiyonel).
- `LOG_LEVEL`: Log seviyesi.
- `WRITE_RAW_EVENTS`: `true` ise `usage_events` koleksiyonuna ham event yazılır (default: false).

## Çalıştırma

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Üretici Servis Entegrasyonu Notları

- `X-Internal-Key` header’ı constant-time compare ile doğrulanır. Env yoksa local/dev modda auth kapalıdır.
- 4xx: payload invalid / auth fail.
- 5xx: Firestore / internal error.
- Producer tarafında usage çağrısını **best-effort** yapın (1-2 sn timeout). Hata olsa bile ana işlem devam etmelidir.
