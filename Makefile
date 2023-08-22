# Update the version in charts/vessl/Chart.yaml first.
release:
	@if [ "`git rev-parse --abbrev-ref HEAD`" != "main" ]; then \
		echo "Not on main branch! Aborting."; \
		exit 1; \
	fi
	@if git diff --exit-code >/dev/null && git diff --cached --exit-code >/dev/null ; then \
		: ; \
	else \
		echo "There are uncommitted changes! Aborting."; \
		exit 1; \
	fi

	@aws sts get-caller-identity > /dev/null
	helm dependency update charts/vessl
	helm package charts/vessl
	aws s3 cp --acl public-read vessl-*.tgz s3://vessl-helm-packages/vessl/
	helm repo index . --merge index.yaml --url https://vessl-helm-packages.s3.ap-northeast-2.amazonaws.com/vessl/
	rm vessl-*.tgz
