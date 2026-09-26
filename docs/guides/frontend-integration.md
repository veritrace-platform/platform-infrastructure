# Frontend Integration

How `enterprise-dashboard`, `driver-mobile-pwa`, and `public-trace-portal` integrate with the backend.
Framework choices inside each frontend repository belong to that repository.

## 1. Base URL and environments

| Environment | API base URL | WebSocket URL |
| --- | --- | --- |
| Local | `http://localhost:8000` | `ws://localhost:8000/ws/v1/notifications` |
| Deployed | `https://api.<domain>` | `wss://api.<domain>/ws/v1/notifications` |

All REST and WebSocket traffic goes through the gateway. Frontends never call service ports directly.

### Testing on a phone

Camera and geolocation APIs work only on HTTPS (or `localhost`). To test the PWA on a real phone:

1. Run the frontend dev server with a rewrite that proxies `/api` and `/ws` to `http://localhost:8000`,
   so there is a single origin.
2. Run `make tunnel TUNNEL_TARGET=http://host.docker.internal:3000` in `platform-infrastructure`.
3. Open the printed `https://….trycloudflare.com` URL on the phone. The URL changes on every run.

## 2. Types from contracts

- REST types are generated from each service's `api/openapi.yaml` with `openapi-typescript`. Do not
  hand-write request or response types.
- Until an endpoint is implemented, it can be mocked from the same document (for example with Prism).
- WebSocket message types follow [messaging.md §6](../contracts/messaging.md#6-websocket-real-time-notifications).

## 3. Authentication

1. `POST /api/v1/auth/login` returns `access_token` (15 min), `refresh_token` (30 days), and the user.
2. Send `Authorization: Bearer <access_token>` on every call.
3. On `401 TOKEN_EXPIRED`, call `POST /api/v1/auth/refresh` once, then retry the request.
   - Refresh tokens rotate: always store the new one.
   - Reusing an old refresh token revokes the whole session.
4. **Storage recommendation:**
   - Keep the refresh token in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie owned by the frontend's own
     server (a Next.js route handler, acting as a backend for the frontend).
   - Keep the access token in memory.
   - Never store tokens in `localStorage`.
5. **WebSocket:** `new WebSocket(url, ["veritrace.v1", "bearer." + accessToken])`. Reconnect with a fresh
   token when the server closes with `4401`.

## 4. Errors

Every error is `application/problem+json` with a stable `code`
([rest-api.md §1.1](../contracts/rest-api.md#11-errors-rfc-9457-problem-details)).

- Map `code` to user-facing text in the frontend.
- Show `trace_id` in error details to help support.
- For form validation, use `errors[].field`.

## 5. Domain rules the UI must mirror

- **GS1 validation** (length and check digit) runs client-side for instant feedback, using the shared test
  vectors in [gs1-identifiers.md](../domain/gs1-identifiers.md#2-check-digit-gs1-modulo-10). The server
  still validates.
- **Pickup** requires a camera scan of the SSCC, the 6-digit code, and a position. Request
  high-accuracy geolocation and send `accuracy_meters`.
- **Recall:** the dashboard must show a blocking banner when a `shipment.recalled` notification arrives.
