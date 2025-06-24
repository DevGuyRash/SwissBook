BATS := $(shell command -v bats 2>/dev/null)

.PHONY: test ci docker-images chmod-tests

chmod-tests:
	@chmod +x tests/*.bats

test: chmod-tests
	@if [ -z "$(BATS)" ]; then \
	    echo "💥 bats not found - install with 'sudo dnf install bats' or 'sudo pacman -S bats'"; \
	    exit 1; \
	 fi
	@$(BATS) tests/*_unit_*.bats

docker-images: chmod-tests
	docker build -f tests/Dockerfile.pw -t ectest:pw tests
	docker build -f tests/Dockerfile.pa -t ectest:pa tests

ci: docker-images
	docker run --rm -v $$PWD/tests:/tests ectest:pw
	docker run --rm -v $$PWD/tests:/tests ectest:pa
