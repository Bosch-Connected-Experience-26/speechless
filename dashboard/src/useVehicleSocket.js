import { useCallback, useEffect, useRef, useState } from "react";

// Connects to the bridge WebSocket and exposes live vehicle state + the command
// feed. The bridge pushes: `snapshot` (full state on connect), `update` (one
// signal changed), `command` (a voice/dashboard action with routing metadata).
// Auto-reconnects so the dashboard survives a bridge restart mid-demo.

const MAX_COMMANDS = 12;

function wsUrl() {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/ws`;
}

export function useVehicleSocket() {
  const [signals, setSignals] = useState({});
  const [commands, setCommands] = useState([]);
  const [status, setStatus] = useState("connecting"); // connecting | open | closed
  const wsRef = useRef(null);
  const retryRef = useRef(null);
  const idRef = useRef(0); // monotonic command id — stable React keys (no ts collision)

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl());
    wsRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => setStatus("open");

    ws.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (msg.type === "snapshot") {
        setSignals(msg.signals || {});
      } else if (msg.type === "update") {
        setSignals((s) => ({ ...s, [msg.path]: msg.value }));
      } else if (msg.type === "command") {
        setSignals((s) => ({ ...s, [msg.path]: msg.value }));
        const id = ++idRef.current;
        setCommands((c) => [{ ...msg, id }, ...c].slice(0, MAX_COMMANDS));
      }
      // `error` frames are non-fatal; surfaced via console for debugging.
      else if (msg.type === "error") {
        console.warn("bridge error:", msg.error);
      }
    };

    ws.onclose = () => {
      setStatus("closed");
      retryRef.current = setTimeout(connect, 1500);
    };
    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(retryRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  // Send a value to the bridge (clicking the car). The bridge echoes it back as
  // an update, so we don't optimistically mutate here.
  const setValue = useCallback((path, value) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "set", path, value }));
    }
  }, []);

  return { signals, commands, status, setValue };
}
