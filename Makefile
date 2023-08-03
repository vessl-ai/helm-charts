release:
	helm dependency update charts/vessl
	helm package charts/vessl
	aws s3 cp --acl public-read vessl-*.tgz s3://vessl-helm-packages/vessl/
	helm repo index . --merge index.yaml --url https://vessl-helm-packages.s3.ap-northeast-2.amazonaws.com/vessl/
	rm vessl-*.tgz
