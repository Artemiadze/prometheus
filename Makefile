.PHONY: sync format lint typecheck arch test openapi-check check

RUNTIME_DIR := apps/prometheus-runtime

sync format lint typecheck arch test openapi-check check:
	$(MAKE) -C $(RUNTIME_DIR) $@
