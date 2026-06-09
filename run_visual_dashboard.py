#!/usr/bin/env python3
"""
Visual Hybrid Voice Assistant Dashboard
=========================================

Web-based dashboard showing:
- Real-time car visualization with vehicle state
- Live sensor metrics and readings
- Voice commands and intent parsing
- Edge vs Cloud routing decisions with reasoning
- Network status and performance metrics
- Live logs of all events
"""

import asyncio
import logging
import json
import os
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from threading import Thread
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'alpacai', 'core'))

from voice_assistant.hybrid_router import (
    HybridVoiceRouter, EdgeCommandExecutor, CloudCommandExecutor,
    NetworkMonitor, VoiceCommand, CommandSafetyCriticality
)
from voice_assistant.vehicle_control import SimulatedVehicleControl
from voice_assistant.intent_parser import VoiceIntentParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global state for dashboard
dashboard_state = {
    "vehicle_state": {},
    "current_command": None,
    "routing_decision": None,
    "network_status": {"latency_ms": 50, "packet_loss": 0.0, "is_connected": True},
    "logs": [],
    "statistics": {},
    "sensor_history": {"speed": [], "temperature": [], "steering": []},
    "routing_history": []
}

max_logs = 50
demo_running = False


class MockCloudService:
    """Mock cloud service"""
    async def route_to_destination(self, destination: str) -> str:
        await asyncio.sleep(0.1)
        return f"Route to {destination} calculated"
    
    async def find_restaurant(self, cuisine: str) -> str:
        await asyncio.sleep(0.1)
        return f"Found 3 {cuisine} restaurants"


def add_log(level: str, message: str, metadata: dict = None):
    """Add log entry with timestamp"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "metadata": metadata or {}
    }
    dashboard_state["logs"].insert(0, entry)
    if len(dashboard_state["logs"]) > max_logs:
        dashboard_state["logs"].pop()
    logger.info(f"[{level}] {message}")


async def run_demo_scenario():
    """Run a realistic demo scenario"""
    global demo_running
    demo_running = True
    
    # Initialize components
    vehicle = SimulatedVehicleControl()
    network = NetworkMonitor()
    parser = VoiceIntentParser()
    
    edge_executor = EdgeCommandExecutor(vehicle)
    cloud_executor = CloudCommandExecutor(MockCloudService(), vehicle)
    router = HybridVoiceRouter(edge_executor, cloud_executor, network)
    
    add_log("INFO", "System initialized", {"components": ["Vehicle", "Network", "Router", "Parser"]})
    
    # Test scenarios
    scenarios = [
        ("Normal network - Emergency brake", "Stop the car immediately", 50, 0.0),
        ("Normal network - Acceleration", "Accelerate to 80 km/h", 50, 0.0),
        ("Normal network - Navigation", "Route me to the airport", 50, 0.0),
        ("Degraded network - Temperature control", "Set temperature to 20 degrees", 300, 0.05),
        ("Degraded network - Steering", "Turn left 45 degrees", 300, 0.05),
        ("Offline - Emergency brake", "Stop the car immediately", 10000, 1.0),
    ]
    
    for description, voice_text, latency, packet_loss in scenarios:
        # Update network conditions
        network.update_metrics(latency, packet_loss)
        dashboard_state["network_status"] = {
            "latency_ms": latency,
            "packet_loss": packet_loss,
            "is_connected": latency < 10000
        }
        
        add_log("NETWORK", f"Network update: {latency}ms latency, {packet_loss*100:.1f}% loss", 
                dashboard_state["network_status"])
        
        await asyncio.sleep(1)  # Delay between commands
        
        # Parse voice command
        command = parser.parse(voice_text)
        if not command:
            add_log("ERROR", f"Failed to parse: {voice_text}")
            continue
        
        dashboard_state["current_command"] = {
            "raw_text": voice_text,
            "intent": command.intent,
            "confidence": command.confidence,
            "criticality": command.criticality.name
        }
        
        add_log("VOICE", f"Command parsed: {command.intent}", {
            "text": voice_text,
            "confidence": command.confidence,
            "criticality": command.criticality.name
        })
        
        await asyncio.sleep(0.5)
        
        # Execute with routing
        result = await router.execute_with_fallback(command)
        
        dashboard_state["routing_decision"] = {
            "intent": command.intent,
            "executed_on": result.executed_on.value,
            "latency_ms": result.latency_ms,
            "success": result.success,
            "response": result.response,
            "fallback_used": result.fallback_used
        }
        
        add_log("ROUTING", f"Executed on {result.executed_on.value}", {
            "intent": command.intent,
            "latency_ms": result.latency_ms,
            "success": result.success
        })
        
        dashboard_state["routing_history"].append(dashboard_state["routing_decision"])
        if len(dashboard_state["routing_history"]) > 20:
            dashboard_state["routing_history"].pop(0)
        
        # Update vehicle state
        dashboard_state["vehicle_state"] = vehicle.get_state()
        
        # Store history for charts
        dashboard_state["sensor_history"]["speed"].append({
            "time": time.time(),
            "value": vehicle.current_speed
        })
        dashboard_state["sensor_history"]["temperature"].append({
            "time": time.time(),
            "value": vehicle.temperature
        })
        dashboard_state["sensor_history"]["steering"].append({
            "time": time.time(),
            "value": vehicle.steering_angle
        })
        
        # Trim history
        for key in dashboard_state["sensor_history"]:
            if len(dashboard_state["sensor_history"][key]) > 30:
                dashboard_state["sensor_history"][key].pop(0)
        
        dashboard_state["statistics"] = router.get_stats()
        
        await asyncio.sleep(1)
    
    demo_running = False
    add_log("INFO", "Demo scenario completed")


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/state')
def get_state():
    """Get current dashboard state"""
    return jsonify(dashboard_state)


@app.route('/api/start-demo')
def start_demo():
    """Start the demo in a background thread"""
    def run_async_demo():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_demo_scenario())
    
    if not demo_running:
        thread = Thread(target=run_async_demo, daemon=True)
        thread.start()
        return jsonify({"status": "Demo started"})
    else:
        return jsonify({"status": "Demo already running"})


# HTML/CSS/JavaScript Dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hybrid Voice Assistant - Visual Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
        }
        
        header {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        h1 {
            font-size: 28px;
            color: #667eea;
            margin-bottom: 10px;
        }
        
        .header-info {
            display: flex;
            gap: 30px;
            align-items: center;
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 15px;
            background: #f0f0f0;
            border-radius: 20px;
            font-size: 14px;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-dot.connected {
            background: #4caf50;
        }
        
        .status-dot.offline {
            background: #f44336;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .demo-button {
            padding: 12px 30px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.3s;
        }
        
        .demo-button:hover {
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        
        .grid {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .card h2 {
            font-size: 16px;
            color: #667eea;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        /* Car Visualization */
        .car-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 300px;
            background: linear-gradient(to bottom, #87CEEB 0%, #E0F6FF 100%);
            border-radius: 10px;
            position: relative;
            overflow: hidden;
        }
        
        svg {
            width: 100%;
            height: 100%;
        }
        
        .speedometer-gauge {
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 15px;
            padding: 10px 0;
        }
        
        .gauge-value {
            font-size: 36px;
            font-weight: bold;
            color: #4cc9f0;
            margin-top: 5px;
            transition: color 0.3s;
        }
        
        .gauge-value.high {
            color: #ff9800;
        }
        
        .gauge-value.critical {
            color: #f44336;
        }
        
        .gauge-label {
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        
        .metric label {
            font-weight: 600;
            color: #666;
            font-size: 13px;
        }
        
        .metric value {
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
        }
        
        .metric.critical value {
            color: #f44336;
            animation: pulse-color 1s infinite;
        }
        
        @keyframes pulse-color {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .routing-badge {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
            color: white;
            margin-top: 10px;
        }
        
        .routing-badge.edge {
            background: #4caf50;
        }
        
        .routing-badge.cloud {
            background: #2196F3;
        }
        
        .routing-badge.parallel {
            background: #9c27b0;
        }
        
        /* Network Status - Signal Bars */
        .signal-container {
            display: flex;
            align-items: flex-end;
            justify-content: center;
            gap: 4px;
            height: 60px;
            margin: 15px 0;
            padding: 10px 0;
        }
        
        .signal-bar {
            width: 14px;
            border-radius: 3px 3px 0 0;
            background: #e0e0e0;
            transition: background 0.4s, height 0.4s;
        }
        
        .signal-bar.active {
            background: #4caf50;
        }
        
        .signal-bar.active.warning {
            background: #ff9800;
        }
        
        .signal-bar.active.critical {
            background: #f44336;
        }
        
        .signal-label {
            text-align: center;
            font-size: 12px;
            font-weight: bold;
            margin-top: 5px;
            color: #4caf50;
            transition: color 0.3s;
        }
        
        .signal-label.warning { color: #ff9800; }
        .signal-label.critical { color: #f44336; }
        .signal-label.offline { color: #f44336; }
        
        /* Logs */
        .logs-container {
            max-height: 400px;
            overflow-y: auto;
            background: #f5f5f5;
            border-radius: 5px;
            padding: 10px;
        }
        
        .log-entry {
            padding: 8px;
            margin-bottom: 5px;
            border-left: 3px solid #667eea;
            background: white;
            border-radius: 3px;
            font-size: 12px;
            animation: slideIn 0.3s;
        }
        
        @keyframes slideIn {
            from { transform: translateX(-10px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes moveLines {
            0% { transform: translateX(0); }
            100% { transform: translateX(-20px); }
        }
        
        @keyframes roadMove {
            0% { transform: translateY(0); }
            100% { transform: translateY(60px); }
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        
        .log-entry.INFO { border-left-color: #2196F3; }
        .log-entry.VOICE { border-left-color: #4CAF50; }
        .log-entry.ROUTING { border-left-color: #FF9800; }
        .log-entry.NETWORK { border-left-color: #9C27B0; }
        .log-entry.ERROR { border-left-color: #F44336; }
        
        .log-time {
            font-size: 11px;
            color: #999;
        }
        
        .log-msg {
            color: #333;
            margin-top: 3px;
        }
        
        .routing-history {
            display: flex;
            gap: 5px;
            margin-top: 10px;
            flex-wrap: wrap;
        }
        
        .routing-dot {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            cursor: pointer;
            transition: all 0.2s;
            border: 2px solid white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .routing-dot:hover {
            transform: scale(1.2);
        }
        
        .routing-dot.edge { background: #4caf50; }
        .routing-dot.cloud { background: #2196F3; }
        .routing-dot.parallel { background: #9c27b0; }
        
        @media (max-width: 1200px) {
            .grid {
                grid-template-columns: 1fr 1fr;
            }
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
        
        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🚗 Hybrid Voice Assistant</h1>
                <p style="color: #666; margin: 0;">Intelligent Edge-Cloud Vehicle Control</p>
            </div>
            <div class="header-info">
                <div class="status-badge">
                    <span class="status-dot connected" id="network-status"></span>
                    <span id="network-info">Connected: 50ms</span>
                </div>
                <button class="demo-button" onclick="startDemo()">▶ Start Demo</button>
            </div>
        </header>
        
        <!-- Main Grid -->
        <div class="grid">
            <!-- Vehicle Visualization -->
            <div class="card">
                <h2>🚗 Vehicle State</h2>
                <div class="car-container" style="background: #1e1e2e; border-radius: 10px; padding: 20px;">
                    <svg viewBox="0 0 300 400" style="width: 100%; max-height: 350px;">
                        <!-- Road -->
                        <rect x="60" y="0" width="180" height="400" fill="#3a3a4a" rx="10"/>
                        <!-- Road dashes (move with speed) -->
                        <g id="road-dashes">
                            <rect x="147" y="20" width="6" height="30" fill="#888" rx="2"/>
                            <rect x="147" y="80" width="6" height="30" fill="#888" rx="2"/>
                            <rect x="147" y="140" width="6" height="30" fill="#888" rx="2"/>
                            <rect x="147" y="200" width="6" height="30" fill="#888" rx="2"/>
                            <rect x="147" y="260" width="6" height="30" fill="#888" rx="2"/>
                            <rect x="147" y="320" width="6" height="30" fill="#888" rx="2"/>
                            <rect x="147" y="380" width="6" height="30" fill="#888" rx="2"/>
                        </g>
                        <!-- Road edges -->
                        <rect x="62" y="0" width="3" height="400" fill="#FFD700" opacity="0.4"/>
                        <rect x="235" y="0" width="3" height="400" fill="#FFD700" opacity="0.4"/>
                        
                        <!-- Car group (rotates with steering) -->
                        <g id="car-container" style="transform-origin: 150px 200px; transition: transform 0.4s ease;">
                            <!-- Shadow -->
                            <ellipse cx="150" cy="205" rx="38" ry="62" fill="rgba(0,0,0,0.3)"/>
                            
                            <!-- Car body -->
                            <rect x="118" y="148" width="64" height="110" fill="#e63946" rx="20"/>
                            <!-- Hood (front tapers) -->
                            <rect x="124" y="138" width="52" height="25" fill="#e63946" rx="14"/>
                            <!-- Trunk (rear tapers slightly) -->
                            <rect x="122" y="248" width="56" height="18" fill="#c1121f" rx="10"/>
                            
                            <!-- Windshield -->
                            <rect x="128" y="158" width="44" height="28" fill="#4cc9f0" rx="8" opacity="0.85"/>
                            <!-- Rear window -->
                            <rect x="130" y="232" width="40" height="20" fill="#4cc9f0" rx="6" opacity="0.7"/>
                            
                            <!-- Roof -->
                            <rect x="132" y="190" width="36" height="38" fill="#a4161a" rx="4"/>
                            
                            <!-- Front wheels (rotate with steering) -->
                            <g id="front-wheels">
                                <rect id="wheel-fl" x="107" y="152" width="12" height="26" fill="#222" rx="4" style="transform-origin: 113px 165px; transition: transform 0.3s;"/>
                                <rect id="wheel-fr" x="181" y="152" width="12" height="26" fill="#222" rx="4" style="transform-origin: 187px 165px; transition: transform 0.3s;"/>
                            </g>
                            <!-- Rear wheels (fixed) -->
                            <rect x="107" y="232" width="12" height="26" fill="#222" rx="4"/>
                            <rect x="181" y="232" width="12" height="26" fill="#222" rx="4"/>
                            
                            <!-- Headlights -->
                            <rect id="headlight-l" x="126" y="136" width="12" height="6" fill="#FFF3B0" rx="3" opacity="0.9"/>
                            <rect id="headlight-r" x="162" y="136" width="12" height="6" fill="#FFF3B0" rx="3" opacity="0.9"/>
                            
                            <!-- Brake lights -->
                            <rect id="brake-l" x="124" y="262" width="10" height="5" fill="#ff6b6b" rx="2" opacity="0.5"/>
                            <rect id="brake-r" x="166" y="262" width="10" height="5" fill="#ff6b6b" rx="2" opacity="0.5"/>
                            
                            <!-- Hazard lights (hidden by default) -->
                            <rect id="hazard-fl" x="115" y="150" width="5" height="5" fill="#FFA500" rx="1" opacity="0"/>
                            <rect id="hazard-fr" x="180" y="150" width="5" height="5" fill="#FFA500" rx="1" opacity="0"/>
                            <rect id="hazard-rl" x="115" y="252" width="5" height="5" fill="#FFA500" rx="1" opacity="0"/>
                            <rect id="hazard-rr" x="180" y="252" width="5" height="5" fill="#FFA500" rx="1" opacity="0"/>
                        </g>
                        
                        <!-- Speed indicator (bottom) -->
                        <text id="steering-angle" x="150" y="395" text-anchor="middle" font-size="13" fill="#aaa" font-family="monospace">
                            Steering: 0°
                        </text>
                    </svg>
                    
                    <!-- Status indicators below car -->
                    <div style="display: flex; justify-content: space-around; margin-top: 10px;">
                        <div id="indicator-speed" style="text-align: center;">
                            <div style="font-size: 22px; font-weight: bold; color: #4cc9f0;" id="speed-display">0</div>
                            <div style="font-size: 11px; color: #888;">km/h</div>
                        </div>
                        <div id="indicator-steering" style="text-align: center;">
                            <div style="font-size: 22px; font-weight: bold; color: #e63946;" id="steer-display">0°</div>
                            <div style="font-size: 11px; color: #888;">steering</div>
                        </div>
                        <div id="indicator-hazard" style="text-align: center;">
                            <div style="font-size: 22px;" id="hazard-display">⚪</div>
                            <div style="font-size: 11px; color: #888;">hazard</div>
                        </div>
                    </div>
                </div>
                
                <!-- Speedometer Gauge -->
                <div class="speedometer-gauge" id="speedometer">
                    <svg viewBox="0 0 200 120" width="220" height="130">
                        <!-- Background arc -->
                        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#eee" stroke-width="12" stroke-linecap="round"/>
                        <!-- Green zone (0-100 km/h) -->
                        <path d="M 20 100 A 80 80 0 0 1 100 20" fill="none" stroke="#4caf50" stroke-width="12" stroke-linecap="round" opacity="0.2"/>
                        <!-- Orange zone (100-150 km/h) -->
                        <path d="M 100 20 A 80 80 0 0 1 155 45" fill="none" stroke="#ff9800" stroke-width="12" stroke-linecap="round" opacity="0.2"/>
                        <!-- Red zone (150-200 km/h) -->
                        <path d="M 155 45 A 80 80 0 0 1 180 100" fill="none" stroke="#f44336" stroke-width="12" stroke-linecap="round" opacity="0.2"/>
                        <!-- Active arc (filled based on speed) -->
                        <path id="speed-arc" d="M 20 100 A 80 80 0 0 1 20 100" fill="none" stroke="#4caf50" stroke-width="12" stroke-linecap="round"/>
                        <!-- Needle -->
                        <line id="speed-needle" x1="100" y1="100" x2="100" y2="30" stroke="#333" stroke-width="2.5" stroke-linecap="round" style="transform-origin: 100px 100px; transition: transform 0.4s ease;"/>
                        <!-- Center dot -->
                        <circle cx="100" cy="100" r="6" fill="#333"/>
                        <circle cx="100" cy="100" r="3" fill="#e63946"/>
                        <!-- Scale labels -->
                        <text x="18" y="115" font-size="9" fill="#888" text-anchor="middle">0</text>
                        <text x="100" y="15" font-size="9" fill="#888" text-anchor="middle">100</text>
                        <text x="182" y="115" font-size="9" fill="#888" text-anchor="middle">200</text>
                    </svg>
                    <div class="gauge-value" id="gauge-speed-value">0</div>
                    <div class="gauge-label">km/h</div>
                </div>
                
                <!-- Quick Metrics -->
                <div class="metric">
                    <label>Current Speed:</label>
                    <value id="metric-speed">0 km/h</value>
                </div>
                <div class="metric">
                    <label>Steering Angle:</label>
                    <value id="metric-steering">0°</value>
                </div>
                <div class="metric">
                    <label>Temperature:</label>
                    <value id="metric-temp">21°C</value>
                </div>
                <div class="metric">
                    <label>Volume:</label>
                    <value id="metric-volume">50%</value>
                </div>
                <div class="metric">
                    <label>Hazard Lights:</label>
                    <value id="metric-hazard">OFF</value>
                </div>
            </div>
            
            <!-- Routing Decisions -->
            <div class="card">
                <h2>🗺️ Routing Decision</h2>
                
                <div id="current-command" style="margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 5px; display: none;">
                    <div style="font-size: 12px; color: #999;">Voice Command:</div>
                    <div id="command-text" style="font-weight: bold; margin-top: 5px;"></div>
                    <div style="font-size: 11px; color: #999; margin-top: 5px;">
                        Intent: <span id="command-intent"></span> | Confidence: <span id="command-conf"></span>
                    </div>
                </div>
                
                <div id="routing-info" style="margin-bottom: 15px; padding: 10px; background: #f5f5f5; border-radius: 5px; display: none;">
                    <div style="font-size: 12px; color: #999;">Executed On:</div>
                    <div id="routing-location" style="font-weight: bold; margin-top: 5px; font-size: 18px;"></div>
                    <div style="font-size: 11px; color: #999; margin-top: 5px;">
                        Latency: <span id="routing-latency"></span> ms
                    </div>
                    <div id="routing-response" style="font-size: 12px; margin-top: 10px; padding: 8px; background: white; border-radius: 3px;"></div>
                    <span id="fallback-badge" class="routing-badge" style="background: #FF9800; display: none;">⚠️ Fallback Used</span>
                </div>
                
                <h3 style="font-size: 14px; margin: 15px 0 10px 0; color: #666;">Decision History</h3>
                <div class="routing-history" id="routing-history"></div>
                
                <h3 style="font-size: 14px; margin: 15px 0 10px 0; color: #666;">Statistics</h3>
                <div class="metric">
                    <label>Total Commands:</label>
                    <value id="stat-total">0</value>
                </div>
                <div class="metric">
                    <label>Edge Executions:</label>
                    <value id="stat-edge">0</value>
                </div>
                <div class="metric">
                    <label>Cloud Executions:</label>
                    <value id="stat-cloud">0</value>
                </div>
                <div class="metric">
                    <label>Success Rate:</label>
                    <value id="stat-success">0%</value>
                </div>
            </div>
            
            <!-- Network & System Status -->
            <div class="card">
                <h2>📡 Network Status</h2>
                
                <div class="metric">
                    <label>Connection:</label>
                    <value id="net-status">Connected</value>
                </div>
                <div class="metric">
                    <label>Latency:</label>
                    <value id="net-latency">50 ms</value>
                </div>
                <div class="metric">
                    <label>Packet Loss:</label>
                    <value id="net-loss">0%</value>
                </div>
                
                <h3 style="font-size: 14px; margin: 15px 0 10px 0; color: #666;">Signal Quality</h3>
                <div class="signal-container" id="signal-container">
                    <div class="signal-bar" id="signal-1" style="height: 20%;"></div>
                    <div class="signal-bar" id="signal-2" style="height: 40%;"></div>
                    <div class="signal-bar" id="signal-3" style="height: 60%;"></div>
                    <div class="signal-bar" id="signal-4" style="height: 80%;"></div>
                    <div class="signal-bar" id="signal-5" style="height: 100%;"></div>
                </div>
                <div class="signal-label" id="signal-label">Excellent</div>
                
                <h3 style="font-size: 14px; margin: 15px 0 10px 0; color: #666;">Voice Recognition</h3>
                <div class="metric">
                    <label>Last Intent:</label>
                    <value id="last-intent">-</value>
                </div>
                <div class="metric">
                    <label>Confidence:</label>
                    <value id="last-confidence">-</value>
                </div>
                <div class="metric">
                    <label>Criticality:</label>
                    <value id="last-criticality">-</value>
                </div>
            </div>
        </div>
        
        <!-- Live Logs -->
        <div class="card" style="margin-bottom: 20px;">
            <h2>📋 Live Event Log</h2>
            <div class="logs-container" id="logs-container"></div>
        </div>
        
        <div class="footer">
            <p>Hybrid Voice Assistant Dashboard | Real-time Edge-Cloud Routing Visualization</p>
        </div>
    </div>
    
    <script>
        let updateInterval;
        
        async function updateDashboard() {
            try {
                const response = await fetch('/api/state');
                const state = await response.json();
                
                // Vehicle State
                if (state.vehicle_state) {
                    const vs = state.vehicle_state;
                    document.getElementById('metric-speed').textContent = vs.speed?.toFixed(1) + ' km/h' || '0 km/h';
                    document.getElementById('metric-steering').textContent = vs.steering_angle?.toFixed(1) + '°' || '0°';
                    document.getElementById('metric-temp').textContent = vs.temperature?.toFixed(1) + '°C' || '21°C';
                    document.getElementById('metric-volume').textContent = vs.volume + '%' || '50%';
                    document.getElementById('metric-hazard').textContent = vs.hazard_lights ? 'ON' : 'OFF' || 'OFF';
                    
                    // Update speedometer
                    updateSpeedometer(vs.speed || 0);
                    
                    // Update car visualization
                    updateCarVisualization(vs);
                }
                
                // Network Status
                if (state.network_status) {
                    const ns = state.network_status;
                    document.getElementById('net-latency').textContent = Math.round(ns.latency_ms) + ' ms';
                    document.getElementById('net-loss').textContent = (ns.packet_loss * 100).toFixed(1) + '%';
                    document.getElementById('net-status').textContent = ns.is_connected ? 'Connected' : 'Offline';
                    
                    const statusDot = document.getElementById('network-status');
                    statusDot.className = 'status-dot ' + (ns.is_connected ? 'connected' : 'offline');
                    
                    document.getElementById('network-info').textContent = `${ns.is_connected ? 'Connected' : 'Offline'}: ${Math.round(ns.latency_ms)}ms`;
                    
                    // Update signal bars (rising bars like phone signal)
                    const signalQuality = Math.max(0, 1 - (ns.latency_ms / 1000));
                    const activeBars = Math.round(signalQuality * 5);
                    
                    let signalClass = '';
                    let signalText = 'No Signal';
                    if (activeBars >= 4) { signalClass = ''; signalText = 'Excellent'; }
                    else if (activeBars === 3) { signalClass = 'warning'; signalText = 'Good'; }
                    else if (activeBars === 2) { signalClass = 'warning'; signalText = 'Fair'; }
                    else if (activeBars === 1) { signalClass = 'critical'; signalText = 'Poor'; }
                    else { signalClass = 'critical'; signalText = 'No Signal'; }
                    
                    for (let i = 1; i <= 5; i++) {
                        const bar = document.getElementById(`signal-${i}`);
                        if (i <= activeBars) {
                            bar.className = `signal-bar active ${signalClass}`;
                        } else {
                            bar.className = 'signal-bar';
                        }
                    }
                    
                    const label = document.getElementById('signal-label');
                    label.textContent = signalText;
                    label.className = `signal-label ${signalClass}`;
                }
                
                // Current Command
                if (state.current_command) {
                    const cc = state.current_command;
                    document.getElementById('current-command').style.display = 'block';
                    document.getElementById('command-text').textContent = '"' + cc.raw_text + '"';
                    document.getElementById('command-intent').textContent = cc.intent;
                    document.getElementById('command-conf').textContent = (cc.confidence * 100).toFixed(0) + '%';
                    document.getElementById('last-intent').textContent = cc.intent;
                    document.getElementById('last-confidence').textContent = (cc.confidence * 100).toFixed(0) + '%';
                    document.getElementById('last-criticality').textContent = cc.criticality;
                }
                
                // Routing Decision
                if (state.routing_decision) {
                    const rd = state.routing_decision;
                    document.getElementById('routing-info').style.display = 'block';
                    
                    const locationDisplay = rd.executed_on.replace(/_/g, ' ').toUpperCase();
                    document.getElementById('routing-location').textContent = locationDisplay;
                    document.getElementById('routing-latency').textContent = rd.latency_ms.toFixed(1);
                    document.getElementById('routing-response').textContent = rd.response || 'Executing...';
                    
                    if (rd.fallback_used) {
                        document.getElementById('fallback-badge').style.display = 'inline-block';
                    } else {
                        document.getElementById('fallback-badge').style.display = 'none';
                    }
                }
                
                // Routing History
                if (state.routing_history && state.routing_history.length > 0) {
                    const historyContainer = document.getElementById('routing-history');
                    historyContainer.innerHTML = '';
                    state.routing_history.forEach(rd => {
                        const dot = document.createElement('div');
                        dot.className = 'routing-dot ' + rd.executed_on.split('_')[0];
                        dot.title = `${rd.intent}: ${rd.executed_on.replace(/_/g, ' ')} (${rd.latency_ms.toFixed(1)}ms)`;
                        historyContainer.appendChild(dot);
                    });
                }
                
                // Statistics
                if (state.statistics) {
                    const stats = state.statistics;
                    document.getElementById('stat-total').textContent = stats.total_commands || 0;
                    document.getElementById('stat-edge').textContent = stats.edge_executions || 0;
                    document.getElementById('stat-cloud').textContent = stats.cloud_executions || 0;
                    document.getElementById('stat-success').textContent = ((stats.success_rate || 0) * 100).toFixed(0) + '%';
                }
                
                // Logs
                if (state.logs && state.logs.length > 0) {
                    const logsContainer = document.getElementById('logs-container');
                    logsContainer.innerHTML = '';
                    state.logs.forEach(log => {
                        const entry = document.createElement('div');
                        entry.className = 'log-entry ' + (log.level || 'INFO');
                        entry.innerHTML = `
                            <div class="log-time">${new Date(log.timestamp).toLocaleTimeString()}</div>
                            <div class="log-msg">${log.message}</div>
                        `;
                        logsContainer.appendChild(entry);
                    });
                }
            } catch (error) {
                console.error('Update error:', error);
            }
        }
        
        function updateSpeedometer(speed) {
            const max = 200;
            const percent = Math.min(speed / max, 1);
            
            // Update needle rotation: -90deg (left, 0 km/h) to +90deg (right, 200 km/h)
            const needleAngle = -90 + (percent * 180);
            const needle = document.getElementById('speed-needle');
            if (needle) {
                needle.style.transform = `rotate(${needleAngle}deg)`;
            }
            
            // Update arc path (sweep from left to current speed)
            const arc = document.getElementById('speed-arc');
            if (arc) {
                const angle = Math.PI - (percent * Math.PI); // pi to 0
                const cx = 100, cy = 100, r = 80;
                const endX = cx + r * Math.cos(angle);
                const endY = cy - r * Math.sin(angle);
                const largeArc = percent > 0.5 ? 1 : 0;
                if (percent > 0.01) {
                    arc.setAttribute('d', `M 20 100 A 80 80 0 ${largeArc} 1 ${endX} ${endY}`);
                } else {
                    arc.setAttribute('d', 'M 20 100 A 80 80 0 0 1 20 100');
                }
                // Color based on speed zone
                if (speed < 100) {
                    arc.setAttribute('stroke', '#4caf50');
                } else if (speed < 150) {
                    arc.setAttribute('stroke', '#ff9800');
                } else {
                    arc.setAttribute('stroke', '#f44336');
                }
            }
            
            // Update digital readout
            const gaugeValue = document.getElementById('gauge-speed-value');
            if (gaugeValue) {
                gaugeValue.textContent = Math.round(speed);
                gaugeValue.className = 'gauge-value' + (speed >= 150 ? ' critical' : speed >= 100 ? ' high' : '');
            }
        }
        
        function updateCarVisualization(vehicleState) {
            const steeringAngle = vehicleState.steering_angle || 0;
            const speed = vehicleState.speed || 0;
            const hazardOn = vehicleState.hazard_lights || false;
            
            // Update text displays
            document.getElementById('steering-angle').textContent = `Steering: ${steeringAngle.toFixed(0)}°`;
            document.getElementById('speed-display').textContent = speed.toFixed(0);
            document.getElementById('steer-display').textContent = steeringAngle.toFixed(0) + '°';
            document.getElementById('hazard-display').textContent = hazardOn ? '🟠' : '⚪';
            
            // Rotate entire car based on steering
            const carContainer = document.getElementById('car-container');
            carContainer.style.transform = `rotate(${steeringAngle * 0.5}deg)`;
            
            // Front wheels turn independently (more visible steering feedback)
            const wheelAngle = steeringAngle * 0.8;
            const wfl = document.getElementById('wheel-fl');
            const wfr = document.getElementById('wheel-fr');
            if (wfl && wfr) {
                wfl.style.transform = `rotate(${wheelAngle}deg)`;
                wfr.style.transform = `rotate(${wheelAngle}deg)`;
            }
            
            // Road dashes animation (simulate forward motion)
            const roadDashes = document.getElementById('road-dashes');
            if (speed > 0) {
                const duration = Math.max(0.3, 3 - (speed / 40));
                roadDashes.style.animation = `roadMove ${duration}s linear infinite`;
            } else {
                roadDashes.style.animation = 'none';
            }
            
            // Brake lights brightness (bright when speed is dropping or 0)
            const brakeOpacity = speed === 0 ? 0.9 : 0.3;
            const brakeL = document.getElementById('brake-l');
            const brakeR = document.getElementById('brake-r');
            if (brakeL && brakeR) {
                brakeL.style.opacity = brakeOpacity;
                brakeR.style.opacity = brakeOpacity;
                brakeL.style.fill = brakeOpacity > 0.5 ? '#ff0000' : '#ff6b6b';
                brakeR.style.fill = brakeOpacity > 0.5 ? '#ff0000' : '#ff6b6b';
            }
            
            // Hazard lights blink
            const hazardElements = ['hazard-fl', 'hazard-fr', 'hazard-rl', 'hazard-rr'];
            hazardElements.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.style.opacity = hazardOn ? '1' : '0';
                    if (hazardOn) {
                        el.style.animation = 'blink 0.6s infinite';
                    } else {
                        el.style.animation = 'none';
                    }
                }
            });
            
            // Headlights glow based on speed
            const headlightOpacity = speed > 0 ? 1 : 0.6;
            const hlL = document.getElementById('headlight-l');
            const hlR = document.getElementById('headlight-r');
            if (hlL && hlR) {
                hlL.style.opacity = headlightOpacity;
                hlR.style.opacity = headlightOpacity;
            }
        }
        
        function startDemo() {
            fetch('/api/start-demo').then(() => {
                console.log('Demo started');
            });
        }
        
        // Start updates
        updateDashboard();
        updateInterval = setInterval(updateDashboard, 500);
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  VISUAL HYBRID VOICE ASSISTANT DASHBOARD")
    print("="*70)
    print("\n🌐 Dashboard running at: http://localhost:5001")
    print("📊 Open this URL in your browser to see real-time visualization\n")
    
    app.run(host='0.0.0.0', port=5001, debug=False)
