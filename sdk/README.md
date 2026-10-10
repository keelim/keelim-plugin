# OpenAI Codex Python SDK 예제

공식 Python SDK `openai-codex`를 사용하는 독립 `uv` 프로젝트입니다. 루트 workspace나 설정에 추가할 필요가 없으며, Python 3.12와 `uv.lock`에 고정한 의존성을 사용합니다. SDK는 기본적으로 패키지와 함께 설치되는 pinned Codex CLI runtime을 사용합니다.

## 준비

keelim-plugin 저장소 루트에서 이 하위 프로젝트로 이동한 뒤 명령을 실행하세요.

```sh
cd sdk
uv sync --frozen
```

SDK는 실행 환경에 이미 설정된 Codex의 ChatGPT 로그인을 사용할 수 있으며, 이 경우 사용량은 ChatGPT 구독 한도에 따릅니다. API 키를 사용하면 OpenAI Platform의 표준 API 과금이 적용되고 ChatGPT 구독에 포함된 사용량과 별도입니다. 이 예제는 로그인, API 키 생성, 자격 증명 저장을 수행하지 않습니다. 자세한 내용은 [Codex 인증 안내](https://learn.chatgpt.com/docs/auth)를 참고하세요.

## 오프라인 검사

모델/API 호출 없이 CLI와 모의 객체 기반 테스트를 확인할 수 있습니다.

```sh
uv run --frozen python -m unittest discover -s tests -v
```

## 실행

이후 모든 `uv` 명령은 `sdk/` 디렉터리에서 실행하세요. 인수를 주지 않거나 `--help`를 사용하면 도움말만 표시됩니다. 프롬프트를 전달하면 Codex 런타임을 시작해 한 번 실행합니다.

```sh
uv run keelim-codex-sdk --help
uv run keelim-codex-sdk "이 저장소의 구조를 설명해줘. 파일은 변경하지 마."
```

예제는 `Sandbox.read_only`와 `ApprovalMode.deny_all`로 파일 변경과 승인된 권한 확대를 막고, 모델을 지정하지 않아 Codex의 기본 모델 선택을 따릅니다. 실제 실행은 네트워크/API 작업이므로 검증 과정에서는 실행하지 않았습니다.

## 참고 문서

- [Codex SDK 공식 문서](https://learn.chatgpt.com/docs/codex-sdk)
- [PyPI: openai-codex](https://pypi.org/project/openai-codex/)
- [인증 및 과금 안내](https://learn.chatgpt.com/docs/auth)
