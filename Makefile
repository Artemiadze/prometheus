.PHONY: sync format lint typecheck arch test check

RUNTIME_DIR := apps/prometheus-runtime

sync format lint typecheck arch test check:
	$(MAKE) -C $(RUNTIME_DIR) $@
