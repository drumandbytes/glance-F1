FROM golang:1.26-alpine AS builder
RUN apk add --no-cache ca-certificates

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o paddock-api .
RUN mkdir /data

# scratch has no CA bundle and no /usr/share/zoneinfo of its own - the CA
# bundle is copied in below, and the binary embeds tzdata itself (see the
# time/tzdata blank import in main.go) since there's nowhere on this image to
# read it from at runtime.
FROM scratch

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
WORKDIR /app
COPY --from=builder /build/paddock-api /app/paddock-api
COPY static ./static

# Durable cache for data that never changes once it exists (finished sessions).
# Owned by the non-root user so a volume mounted here is writable; without a
# volume it just lives in the container's writable layer.
COPY --from=builder --chown=65532:65532 /data /data
ENV CACHE_DIR=/data

EXPOSE 4463
USER 65532:65532

ENTRYPOINT ["/app/paddock-api"]
