.PHONY: \
	sync format lint typecheck arch test openapi-check build check \
	runtime-sync runtime-format runtime-lint runtime-typecheck runtime-arch runtime-test runtime-test-domain runtime-openapi-check runtime-check \
	runtime-frozen \
	evals-sync evals-format evals-lint evals-typecheck evals-test evals-retrieval evals-rag evals-perf evals-check \
	plugin-sync plugin-lint plugin-typecheck plugin-test plugin-build plugin-check

RUNTIME_DIR := apps/prometheus-runtime
EVALS_DIR := evals
PLUGIN_DIR := apps/prometheus-plugin

runtime-sync:
	$(MAKE) -C $(RUNTIME_DIR) sync

runtime-format:
	$(MAKE) -C $(RUNTIME_DIR) format

runtime-lint:
	$(MAKE) -C $(RUNTIME_DIR) lint

runtime-typecheck:
	$(MAKE) -C $(RUNTIME_DIR) typecheck

runtime-arch:
	$(MAKE) -C $(RUNTIME_DIR) arch

runtime-test:
	$(MAKE) -C $(RUNTIME_DIR) test

runtime-test-domain:
	$(MAKE) -C $(RUNTIME_DIR) test-domain

runtime-openapi-check:
	$(MAKE) -C $(RUNTIME_DIR) openapi-check

runtime-check: runtime-lint runtime-typecheck runtime-arch runtime-test runtime-openapi-check runtime-test-domain

evals-sync:
	$(MAKE) -C $(EVALS_DIR) sync

evals-format:
	$(MAKE) -C $(EVALS_DIR) format

evals-lint:
	$(MAKE) -C $(EVALS_DIR) lint

evals-typecheck:
	$(MAKE) -C $(EVALS_DIR) typecheck

evals-test:
	$(MAKE) -C $(EVALS_DIR) test

evals-retrieval:
	$(MAKE) -C $(EVALS_DIR) retrieval

evals-rag:
	$(MAKE) -C $(EVALS_DIR) rag

evals-perf:
	$(MAKE) -C $(EVALS_DIR) perf

evals-check: evals-lint evals-typecheck evals-test evals-retrieval evals-rag evals-perf

runtime-frozen:
	uv sync --project $(RUNTIME_DIR) --group packaging --group dev
	uv run --project $(RUNTIME_DIR) --group packaging python packaging/build_frozen.py

plugin-sync:
	npm --prefix $(PLUGIN_DIR) ci

plugin-lint:
	npm --prefix $(PLUGIN_DIR) run lint

plugin-typecheck:
	npm --prefix $(PLUGIN_DIR) run typecheck

plugin-test:
	npm --prefix $(PLUGIN_DIR) run test

plugin-build:
	npm --prefix $(PLUGIN_DIR) run build

plugin-check:
	npm --prefix $(PLUGIN_DIR) run check

sync: runtime-sync plugin-sync
format: runtime-format
	npm --prefix $(PLUGIN_DIR) run lint:fix
lint: runtime-lint plugin-lint
typecheck: runtime-typecheck plugin-typecheck
arch: runtime-arch
test: runtime-test plugin-test
openapi-check: runtime-openapi-check
build: plugin-build
check: runtime-check evals-check plugin-check
