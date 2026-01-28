.PHONY: all build test clean proto install

BINARY_NAME=quant
BUILD_DIR=./build
PROTO_DIR=./pkg/proto

all: proto build

build:
	@echo "Building $(BINARY_NAME)..."
	@mkdir -p $(BUILD_DIR)
	go build -ldflags="-s -w" -o $(BUILD_DIR)/$(BINARY_NAME) cmd/quant/main.go
	@echo "Build complete: $(BUILD_DIR)/$(BINARY_NAME)"

test:
	@echo "Running tests..."
	go test -v ./...

bench:
	@echo "Running benchmarks..."
	go test -bench=. -benchmem ./...

proto:
	@echo "Generating protobuf files..."
	@mkdir -p $(PROTO_DIR)
	protoc --go_out=. --go_opt=paths=source_relative \
		--go-grpc_out=. --go-grpc_opt=paths=source_relative \
		$(PROTO_DIR)/*.proto

clean:
	@echo "Cleaning..."
	@rm -rf $(BUILD_DIR)
	@rm -f *.db *.prof
	go clean

install: build
	@echo "Installing $(BINARY_NAME)..."
	@cp $(BUILD_DIR)/$(BINARY_NAME) $(GOPATH)/bin/
	@echo "Installed to $(GOPATH)/bin/$(BINARY_NAME)"

run: build
	$(BUILD_DIR)/$(BINARY_NAME)

# Development commands
dev:
	go run cmd/quant/main.go

fmt:
	go fmt ./...

lint:
	golangci-lint run

# Performance profiling
profile-cpu:
	go test -cpuprofile=cpu.prof -bench=.
	go tool pprof cpu.prof

profile-mem:
	go test -memprofile=mem.prof -bench=.
	go tool pprof mem.prof

# Docker support
docker-build:
	docker build -t quant-researcher .

docker-run:
	docker run -p 8080:8080 -p 50051:50051 quant-researcher