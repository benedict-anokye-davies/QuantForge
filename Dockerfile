# Build stage
FROM golang:1.21-alpine AS builder

RUN apk add --no-cache git make protobuf

WORKDIR /app

# Copy go mod files
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build
RUN make build

# Runtime stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /root/

# Copy binary from builder
COPY --from=builder /app/build/quant .
COPY --from=builder /app/configs ./configs

# Expose ports
EXPOSE 8080 8081 50051

# Run
CMD ["./quant"]