package main

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

const durableTTL = 30 * 24 * time.Hour

type cacheEntry struct {
	data      any
	expiresAt time.Time
}

type cacheStore struct {
	mu    sync.RWMutex
	store map[string]cacheEntry
	dir   string
}

func newCache(dir string) *cacheStore {
	return &cacheStore{store: make(map[string]cacheEntry), dir: dir}
}

func (c *cacheStore) get(key string, now time.Time) (any, bool) {
	c.mu.RLock()
	entry, ok := c.store[key]
	c.mu.RUnlock()
	if !ok || !now.Before(entry.expiresAt) {
		if ok {
			c.mu.Lock()
			delete(c.store, key)
			c.mu.Unlock()
		}
		return nil, false
	}
	return entry.data, true
}

func (c *cacheStore) set(key string, value any, expiresAt time.Time) {
	c.mu.Lock()
	c.store[key] = cacheEntry{data: value, expiresAt: expiresAt}
	c.mu.Unlock()
}

// getDurable/setDurable are for data that never changes once it exists (a
// finished session's results). Kept in memory like any entry and, when a
// directory is configured, mirrored to disk so it survives a restart - the
// upstream (OpenF1) can be unreachable for long stretches around sessions.
func (c *cacheStore) getDurable(key string, now time.Time) (any, bool) {
	if value, ok := c.get(key, now); ok {
		return value, true
	}
	if c.dir == "" {
		return nil, false
	}
	path := c.path(key)
	info, err := os.Stat(path)
	if err != nil || now.Sub(info.ModTime()) > durableTTL {
		return nil, false
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, false
	}
	var value any
	if json.Unmarshal(data, &value) != nil {
		return nil, false
	}
	c.set(key, value, now.Add(durableTTL))
	return value, true
}

func (c *cacheStore) setDurable(key string, value any, now time.Time) error {
	c.set(key, value, now.Add(durableTTL))
	if c.dir == "" {
		return nil
	}
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(c.dir, 0o755); err != nil {
		return err
	}
	tmp, err := os.CreateTemp(c.dir, ".tmp-*")
	if err != nil {
		return err
	}
	_, writeErr := tmp.Write(data)
	closeErr := tmp.Close()
	if err := errors.Join(writeErr, closeErr); err != nil {
		os.Remove(tmp.Name())
		return err
	}
	return os.Rename(tmp.Name(), c.path(key))
}

func (c *cacheStore) path(key string) string {
	safe := strings.Map(func(r rune) rune {
		if r >= 'a' && r <= 'z' || r >= 'A' && r <= 'Z' || r >= '0' && r <= '9' || r == '-' || r == '_' {
			return r
		}
		return '_'
	}, key)
	return filepath.Join(c.dir, safe+".json")
}

// probe checks the cache directory can actually be written to.
func (c *cacheStore) probe() error {
	if err := os.MkdirAll(c.dir, 0o755); err != nil {
		return err
	}
	f, err := os.CreateTemp(c.dir, ".probe-*")
	if err != nil {
		return err
	}
	f.Close()
	return os.Remove(f.Name())
}
