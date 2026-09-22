package main

import (
	"sync"
	"time"
)

type cacheEntry struct {
	data      any
	expiresAt time.Time
}

type cacheStore struct {
	mu    sync.RWMutex
	store map[string]cacheEntry
}

func newCache() *cacheStore {
	return &cacheStore{store: make(map[string]cacheEntry)}
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
