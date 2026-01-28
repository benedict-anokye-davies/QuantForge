package server

import (
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// WebSocketServer handles WebSocket connections for real-time updates
type WebSocketServer struct {
	upgrader    websocket.Upgrader
	clients     map[*Client]bool
	broadcast   chan Message
	register    chan *Client
	unregister  chan *Client
	mu          sync.RWMutex
	
	// Data sources
	priceFeeds  map[string]chan PriceUpdate
}

type Client struct {
	conn   *websocket.Conn
	send   chan Message
	server *WebSocketServer
	subs   map[string]bool
	mu     sync.RWMutex
}

type Message struct {
	Type    string      `json:"type"`
	Symbol  string      `json:"symbol,omitempty"`
	Data    interface{} `json:"data"`
	Timestamp int64     `json:"timestamp"`
}

type PriceUpdate struct {
	Symbol    string  `json:"symbol"`
	Price     float64 `json:"price"`
	Volume    float64 `json:"volume"`
	Bid       float64 `json:"bid"`
	Ask       float64 `json:"ask"`
	Timestamp int64   `json:"timestamp"`
}

type SignalUpdate struct {
	Symbol     string  `json:"symbol"`
	Strategy   string  `json:"strategy"`
	Action     string  `json:"action"`
	Confidence float64 `json:"confidence"`
	Price      float64 `json:"price"`
	Timestamp  int64   `json:"timestamp"`
}

type PortfolioUpdate struct {
	Cash       float64            `json:"cash"`
	Equity     float64            `json:"equity"`
	TotalValue float64            `json:"total_value"`
	Positions  map[string]Position `json:"positions"`
	Timestamp  int64              `json:"timestamp"`
}

type Position struct {
	Symbol       string  `json:"symbol"`
	Quantity     float64 `json:"quantity"`
	EntryPrice   float64 `json:"entry_price"`
	CurrentPrice float64 `json:"current_price"`
	UnrealizedPnL float64 `json:"unrealized_pnl"`
}

func NewWebSocketServer() *WebSocketServer {
	return &WebSocketServer{
		upgrader: websocket.Upgrader{
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
			CheckOrigin: func(r *http.Request) bool {
				return true // Allow all origins in development
			},
		},
		clients:    make(map[*Client]bool),
		broadcast:  make(chan Message, 10000),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		priceFeeds: make(map[string]chan PriceUpdate),
	}
}

func (ws *WebSocketServer) Start(address string) {
	// Start hub
	go ws.run()
	
	// Setup HTTP handlers
	http.HandleFunc("/ws", ws.handleWebSocket)
	http.HandleFunc("/health", ws.handleHealth)
	
	go func() {
		if err := http.ListenAndServe(address, nil); err != nil {
			fmt.Printf("WebSocket server error: %v\n", err)
		}
	}()
}

func (ws *WebSocketServer) run() {
	for {
		select {
		case client := <-ws.register:
			ws.mu.Lock()
			ws.clients[client] = true
			ws.mu.Unlock()
			fmt.Printf("Client connected. Total: %d\n", len(ws.clients))
			
		case client := <-ws.unregister:
			ws.mu.Lock()
			if _, ok := ws.clients[client]; ok {
				delete(ws.clients, client)
				close(client.send)
			}
			ws.mu.Unlock()
			fmt.Printf("Client disconnected. Total: %d\n", len(ws.clients))
			
		case message := <-ws.broadcast:
			ws.mu.RLock()
			for client := range ws.clients {
				select {
				case client.send <- message:
				default:
					// Client buffer full, close connection
					close(client.send)
					delete(ws.clients, client)
				}
			}
			ws.mu.RUnlock()
		}
	}
}

func (ws *WebSocketServer) handleWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := ws.upgrader.Upgrade(w, r, nil)
	if err != nil {
		fmt.Printf("WebSocket upgrade error: %v\n", err)
		return
	}
	
	client := &Client{
		conn:   conn,
		send:   make(chan Message, 256),
		server: ws,
		subs:   make(map[string]bool),
	}
	
	ws.register <- client
	
	// Start goroutines for client
	go client.writePump()
	go client.readPump()
}

func (ws *WebSocketServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("OK"))
}

// BroadcastPrice sends price update to all subscribed clients
func (ws *WebSocketServer) BroadcastPrice(update PriceUpdate) {
	msg := Message{
		Type:      "price",
		Symbol:    update.Symbol,
		Data:      update,
		Timestamp: time.Now().UnixNano(),
	}
	
	ws.broadcast <- msg
}

// BroadcastSignal sends trading signal to all clients
func (ws *WebSocketServer) BroadcastSignal(signal SignalUpdate) {
	msg := Message{
		Type:      "signal",
		Symbol:    signal.Symbol,
		Data:      signal,
		Timestamp: time.Now().UnixNano(),
	}
	
	ws.broadcast <- msg
}

// BroadcastPortfolio sends portfolio update to all clients
func (ws *WebSocketServer) BroadcastPortfolio(portfolio PortfolioUpdate) {
	msg := Message{
		Type:      "portfolio",
		Data:      portfolio,
		Timestamp: time.Now().UnixNano(),
	}
	
	ws.broadcast <- msg
}

func (c *Client) readPump() {
	defer func() {
		c.server.unregister <- c
		c.conn.Close()
	}()
	
	c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
		return nil
	})
	
	for {
		var msg map[string]interface{}
		err := c.conn.ReadJSON(&msg)
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				fmt.Printf("WebSocket error: %v\n", err)
			}
			break
		}
		
		// Handle client messages (subscriptions, etc.)
		c.handleMessage(msg)
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(54 * time.Second)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()
	
	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			
			c.conn.WriteJSON(message)
			
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

func (c *Client) handleMessage(msg map[string]interface{}) {
	msgType, ok := msg["type"].(string)
	if !ok {
		return
	}
	
	switch msgType {
	case "subscribe":
		if symbol, ok := msg["symbol"].(string); ok {
			c.mu.Lock()
			c.subs[symbol] = true
			c.mu.Unlock()
		}
		
	case "unsubscribe":
		if symbol, ok := msg["symbol"].(string); ok {
			c.mu.Lock()
			delete(c.subs, symbol)
			c.mu.Unlock()
		}
	}
}

// SubscribePriceFeed subscribes to a price feed for a symbol
func (ws *WebSocketServer) SubscribePriceFeed(symbol string) chan PriceUpdate {
	ch := make(chan PriceUpdate, 1000)
	ws.priceFeeds[symbol] = ch
	return ch
}