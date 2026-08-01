import { realtimeUrl, type AuthenticatedApi } from "./api";

export type RealtimeEvent =
  | { type: "submission.created" }
  | { type: "submission.updated" }
  | { type: "points.changed" }
  | { type: "redemption.created" }
  | { type: "redemption.updated" }
  | { type: "chores.changed" }
  | { type: "rewards.changed" }
  | { type: "children.changed" };

const EVENT_TYPES = new Set<RealtimeEvent["type"]>([
  "submission.created",
  "submission.updated",
  "points.changed",
  "redemption.created",
  "redemption.updated",
  "chores.changed",
  "rewards.changed",
  "children.changed",
]);

export function parseRealtimeEvent(value: unknown): RealtimeEvent | null {
  if (!value || typeof value !== "object" || !("type" in value)) return null;
  const type = value.type;
  return typeof type === "string" && EVENT_TYPES.has(type as RealtimeEvent["type"])
    ? { type: type as RealtimeEvent["type"] }
    : null;
}

export class RealtimeClient {
  private socket: WebSocket | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private retryAttempt = 0;
  private stopped = true;

  constructor(
    private readonly api: AuthenticatedApi,
    private readonly onEvent: (event: RealtimeEvent) => void,
  ) {}

  start() {
    if (!this.stopped) return;
    this.stopped = false;
    void this.connect();
  }

  stop() {
    this.stopped = true;
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
    const socket = this.socket;
    this.socket = null;
    socket?.close(1000, "App inactive");
  }

  private async connect() {
    try {
      const { ticket } = await this.api<{ ticket: string }>("/realtime/ticket", {
        method: "POST",
      });
      if (this.stopped) return;

      const socket = new WebSocket(realtimeUrl(ticket));
      this.socket = socket;
      socket.onopen = () => {
        if (this.socket === socket) this.retryAttempt = 0;
      };
      socket.onmessage = (message) => {
        try {
          const event = parseRealtimeEvent(JSON.parse(String(message.data)));
          if (event) this.onEvent(event);
        } catch {
          // Ignore malformed invalidation hints. REST queries remain authoritative.
        }
      };
      socket.onerror = () => socket.close();
      socket.onclose = () => {
        if (this.socket === socket) this.socket = null;
        if (!this.stopped) this.scheduleReconnect();
      };
    } catch {
      if (!this.stopped) this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    if (this.retryTimer || this.stopped) return;
    const baseDelay = Math.min(30_000, 1_000 * 2 ** this.retryAttempt);
    const delay = Math.round(baseDelay * (0.75 + Math.random() * 0.5));
    this.retryAttempt += 1;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.connect();
    }, delay);
  }
}
