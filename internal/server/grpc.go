package server

import (
	"context"
	"fmt"
	"net"

	"google.golang.org/grpc"
)

// GRPCServer implements the quant gRPC service
type GRPCServer struct {
	engine    ExecutionEngine
	dataStore DataStore
	
	server *grpc.Server
}

type ExecutionEngine interface {
	Start() error
	Stop() error
	SubmitTick(symbol string, price, volume, bid, ask float64)
	GetPortfolio() interface{}
	GetMetrics() interface{}
}

type DataStore interface {
	GetTicks(symbol string, start, end int64) ([]interface{}, error)
	StoreTick(tick interface{}) error
	GetTrades(strategyID string) ([]interface{}, error)
	StoreTrade(trade interface{}) error
}

func NewGRPCServer(engine ExecutionEngine, dataStore DataStore) *GRPCServer {
	return &GRPCServer{
		engine:    engine,
		dataStore: dataStore,
	}
}

func (s *GRPCServer) Start(address string) error {
	listener, err := net.Listen("tcp", address)
	if err != nil {
		return fmt.Errorf("failed to listen: %w", err)
	}
	
	s.server = grpc.NewServer(
		grpc.MaxConcurrentStreams(1000),
	)
	
	go func() {
		if err := s.server.Serve(listener); err != nil {
			fmt.Printf("gRPC server error: %v\n", err)
		}
	}()
	
	return nil
}

func (s *GRPCServer) Stop() {
	if s.server != nil {
		s.server.GracefulStop()
	}
}

// HealthCheck for gRPC health checking
func (s *GRPCServer) HealthCheck(ctx context.Context) (bool, error) {
	return true, nil
}