# Patch2Proof v0.4 — Thiết kế pipeline và tài liệu bàn giao nghiên cứu

## 0. Cách đọc tài liệu

Patch2Proof hỗ trợ nghiên cứu tái hiện 1-day trong lab cục bộ được ủy quyền. Mục tiêu là đi từ patch và mã nguồn đã ghim phiên bản tới một kết quả kiểm chứng có đối chứng, có thể kiểm toán. “PoC hoàn chỉnh” ở đây nghĩa là kế hoạch tái hiện cục bộ đầy đủ và, khi có adapter được duyệt, quan sát runtime trên cặp bản dễ bị ảnh hưởng và bản đã sửa. Nó không có nghĩa là khai thác mục tiêu thật.

| Nhãn | Ý nghĩa |
|---|---|
| **Đã có trong scaffold** | Có mã hoặc contract trong workspace; cần xem implementation/test trước khi dựa vào nó trong nghiên cứu. |
| **Thiết kế** | Kiến trúc hoặc policy đã xác định, nhưng có thể thiếu worker, adapter, lưu trữ hoặc độ phủ ngôn ngữ. |
| **Việc cần làm** | Hạng mục ưu tiên để tăng chất lượng nghiên cứu, an toàn hoặc khả năng tái lập. |

Tài liệu này cùng tồn tại với tài liệu module trong thư mục docs. Khi implementation thay đổi, cập nhật handoff và module docs trong cùng một thay đổi để tránh mâu thuẫn.

## 1. Tóm tắt dự án

### 1.1 Vấn đề

Tái hiện 1-day từ patch là bài toán nhiều giai đoạn: xác định chính xác hai revision; hiểu patch sửa gì và vì sao; nối vùng đổi tới entrypoint; dựng môi trường lặp lại được; chuyển hypothesis thành kiểm tra an toàn; phân biệt trigger thật với crash/cấu hình/mô phỏng; và báo cáo kết luận cùng bằng chứng.

LLM có thể đọc source và đề xuất hypothesis, nhưng câu trả lời tự tin không phải bằng chứng. Container chạy thành công cũng chưa chứng minh lỗ hổng tồn tại. Patch2Proof tách reasoning, execution và proof.

### 1.2 Mục tiêu sản phẩm

Đầu vào: case manifest trỏ tới repository/fixture, hai revision đã ghim, patch/advisory, build context và adapter đã đăng ký.

Đầu ra: artifacts theo từng lần thử và báo cáo Markdown/JSON có verdict:

- **confirmed** — đủ bằng chứng và đối chứng.
- **candidate** — giả thuyết có cơ sở nhưng thiếu ít nhất một gate.
- **rejected** — giả thuyết bị phản chứng bởi source hoặc kiểm tra xác định.
- **blocked** — policy, quyền hoặc đầu vào không cho phép tiếp tục.
- **not_executed** — chưa thu thập runtime evidence.

Mặc định fail-closed: thiếu provider, source mapping, adapter, policy hoặc approval thì hạ verdict/dừng; không tự nâng quyền hay đoán kết quả.

### 1.3 Luận điểm thiết kế

Đóng góp nghiên cứu không phải “dùng LangGraph” hay “gọi LLM để sinh PoC”. Luận điểm cần kiểm chứng là:

> Pipeline patch-guided có thể cải thiện khả năng tái hiện và độ tin cậy của kết luận nếu kết hợp mapping đầy đủ patch sang hai revision, điều tra caller/callee có công cụ, lập kế hoạch theo graph các nghĩa vụ nhân quả còn thiếu, ghi failure có cấu trúc, và xác nhận bằng cùng một PoC trên cặp vulnerable/fixed với oracle độc lập.

Đây là giả thuyết nghiên cứu, chưa phải kết quả; cần benchmark, ablation và reviewer labels.

## 2. Phạm vi và thuật ngữ

### 2.1 Trong phạm vi

- 1-day dựa trên patch/advisory đã công bố.
- Repository được cung cấp rõ ràng; revision được ghim.
- Chạy trong lab riêng hoặc môi trường kiểm thử được ủy quyền.
- Mô hình đọc patch/source và gọi truy vấn source chỉ đọc đã định nghĩa.
- Sinh SafePoC theo tập hành động giới hạn, gọi adapter đã đăng ký.
- Dựng cặp môi trường vulnerable/fixed, so sánh kết quả.
- Sinh báo cáo có liên kết tới artifacts, evidence và uncertainty.

### 2.2 Ngoài phạm vi mặc định

- Tương tác dịch vụ công cộng, mục tiêu thật hoặc mạng nội bộ ngoài lab.
- Shell tùy ý, khai thác tổng quát, persistence, lấy credential hoặc thay đổi dữ liệu ngoài case.
- Tự sửa source/policy để làm thử nghiệm thành công.
- Xem LLM là bộ xác nhận.
- Xem static call graph là bằng chứng runtime reachability.

### 2.3 Thuật ngữ

| Thuật ngữ | Định nghĩa |
|---|---|
| **Patch-complete** | Giữ nguyên toàn bộ diff đầu vào và ghi nhận mọi hunk; không bỏ hunk khó hoặc chỉ gửi tóm tắt vào reasoning. |
| **Source context** | Mapping hunk sang source của vulnerable/fixed, changed symbols, slices, caller/callee candidates, tests và provenance. |
| **Evidence** | Quan sát có nguồn, revision, vị trí hoặc artifact hash. |
| **Hypothesis** | Suy luận chưa xác nhận về điều kiện, đường đi hoặc chuyển trạng thái gây lỗi. |
| **SafePoC** | IR giới hạn hành động, không có trường thực thi shell tổng quát. |
| **Semantic oracle** | Bộ xác nhận state bảo mật mục tiêu, không chỉ exit code hoặc crash. |
| **Counterfactual** | Cùng plan/PoC trên revision đã sửa hoặc fixture âm để kiểm tra tính đặc hiệu. |
| **FCSM** | Failure-Conditioned Skill Memory: memory chiến lược sửa plan dựa trên failure class và graph edge chưa đạt. |
| **Proof bundle** | Artifact máy đọc được, dựng bằng logic xác định từ evidence, coverage và validation; không do LLM kết luận. |

## 3. Câu hỏi nghiên cứu và đóng góp

### 3.1 Gaps cần kiểm tra

1. **Từ patch tới đường đi:** patch cho thấy vùng đổi; cần nối vùng đó với entrypoint và state transition bằng source evidence.
2. **Static relation chưa đủ:** caller/callee từ parser là ứng viên; phải tách candidate edge khỏi runtime-reached edge.
3. **Thử sai thiếu ngữ nghĩa:** feedback “không chạy” không phân biệt dependency, precondition, reachability hay oracle.
4. **Xác nhận bề mặt:** exit code/log/crash có thể tạo false positive; cần semantic delta và fixed counterfactual.
5. **Tái sử dụng chiến lược:** bài học failure nên lưu thành thao tác an toàn kiểm chứng được, không lưu payload hay coi retrieval là proof.
6. **Tái lập:** cần lưu revisions, image digest, prompt version, plan hash, observations và điều kiện chạy lại.

### 3.2 Contributions có thể ablate

- **C1 — Patch-complete source investigation:** mapping hunk sang vulnerable/fixed, backward callers, forward callees, bounded read-only tool loop.
- **C2 — Directed reproduction graph:** nghĩa vụ từ source attribution qua precondition/reachability/semantic transition tới oracle/counterfactual.
- **C3 — Failure-conditioned repair:** validator định failure class/missing transition; LLM chỉ xếp hạng operator đã cho phép.
- **C4 — Differential proof protocol:** cùng SafePoC, fixture và policy trên hai revision; oracle độc lập quyết định semantic delta.
- **C5 — Auditable evidence bundle:** claim trong report trỏ tới evidence.

Novelty chỉ khẳng định sau systematic comparison. Tránh tuyên bố “đầu tiên” nếu chưa kiểm tra literature đầy đủ.

### 3.3 Research questions

| RQ | Câu hỏi | Metrics |
|---|---|---|
| RQ1 | Mapping patch và source investigation hai chiều có cải thiện định vị/hypothesis so với diff-only không? | hunk-to-symbol precision/recall, path precision/recall theo depth, citation accuracy |
| RQ2 | Directed graph và missing-transition repair có cải thiện completion trong cùng budget không? | edge coverage, attempts tới differential pass, time/token/cost |
| RQ3 | FCSM có giảm lặp failure và chuyển strategy sang held-out family không? | retrieval precision@k, repeated failure, transfer, regression |
| RQ4 | Paired semantic oracle có giảm false confirmation so với vulnerable-only/exit-code-only không? | confirmation precision, oracle specificity, false positives |
| RQ5 | SafePoC/worker policy có duy trì hiệu quả trong khi giới hạn tác động ngoài case không? | policy violations, blocked-action accuracy |
| RQ6 | Evidence bundle có giúp reviewer nhanh và thống nhất hơn không? | unsupported-claim rate, agreement, review time |

Không gộp tất cả thành một chỉ số “PoC success”. Mỗi RQ cần dataset split, baseline và metric riêng.

## 4. Kiến trúc tổng thể

Patch2Proof dùng ba loại graph độc lập:

1. **LangGraph orchestration graph:** thứ tự node, routing, interrupt, retry budget và checkpoint.
2. **Agent/tool loop:** model xem patch/source, gọi truy vấn source đã định nghĩa, đọc kết quả và cập nhật hypothesis.
3. **Directed reproduction graph:** các trạng thái/quan hệ nhân quả cần chứng minh cho một case.

LangGraph workflow chỉ cho biết workflow đi qua node; không chứng minh lỗ hổng được tái hiện. Reproduction graph cùng runtime evidence và oracle quyết định coverage.

### 4.1 Thành phần

~~~mermaid
flowchart TD
    A["Case manifest + pinned revisions"] --> B["LangGraph orchestration"]
    B --> C["Patch/source investigator"]
    C --> D["Evidence + hypothesis contracts"]
    D --> E["Reproduction graph + SafePoC plan"]
    E --> F["Paired worker + independent oracle"]
    F --> G["Proof bundle + reviewed report"]
~~~

| Plane | Trách nhiệm | Quyền hạn |
|---|---|---|
| **Reasoning** | Phân tích patch/source, hypothesis, missing transition, plan. | LLM đọc đầu vào xác định; chỉ typed read-only queries. |
| **Control** | LangGraph, budgets, interrupts, routing. | Node khai báo, typed state, checkpointer. |
| **Execution** | Build/run theo policy; lấy observations qua adapter. | Không nhận shell string từ model; giới hạn tài nguyên. |
| **Evidence** | Lưu identities, logs, graph snapshots, hashes, verdict. | Provenance; claim phải trỏ tới evidence. |

### 4.2 Trust boundaries

~~~mermaid
flowchart TD
    A["Untrusted patch, repo, advisory, build files"] --> B["Read-only ingestion and analysis"]
    B --> C["Typed model decision and query validator"]
    C --> D["Reviewed adapter and worker policy"]
    D --> E["Disposable vulnerable/fixed pair"]
    E --> F["Independent observations and proof predicate"]
~~~

Patch, advisory, README, comments, Dockerfile, tool result và model output là dữ liệu không tin cậy cho tới khi kiểm tra. Nội dung repository không được phép thay system policy.

## 5. LangGraph orchestration

### 5.1 Luồng

~~~mermaid
flowchart TD
    A["preflight → ingest → analysis"] --> B["source_context"]
    B --> C["reasoning → reproduction_graph"]
    C --> D["knowledge → skill_retrieval → poc_reasoning"]
    D --> E["environment_plan → build_approval → build"]
    E --> F["poc → attempt_plan → execution_approval"]
    F --> G["validate → feedback → skeptic"]
    G --> H["repair_reasoning → repair → attempt_plan"]
    G --> I["skill_update → report"]
~~~

Nhánh có thể kết thúc sớm bằng report khi policy block, source context thiếu, approval bị từ chối hoặc execution chưa được phép. Repair chỉ chạy khi validator ghi failure/incomplete coverage và còn budget.

### 5.2 Contract theo node

| Node | Đầu vào | Công việc | Đầu ra/điều kiện |
|---|---|---|---|
| **preflight** | CaseManifest | Authorization, policy network, paths, output root. | ready hoặc blocked; mặc định network none. |
| **ingest** | Repo/revisions hoặc fixture | Giữ toàn bộ diff, identities. | raw patch, source identities, patch hash. |
| **analysis** | Raw patch | Parse file/hunk/line ranges, security-relevant changes. | patch analysis và parser completeness. |
| **source_context** | Diff + pinned source | Verify hunks, symbols, caller/callee slices, query index. | SourceContextBundle hoặc missing-context reasons. |
| **reasoning** | Full diff + source + evidence | Hypotheses cạnh tranh, evidence, uncertainty, disconfirmation, next action. | AgentReasoning + Hypothesis typed. |
| **reproduction_graph** | Hypothesis + evidence | Tạo causal obligations và coverage ban đầu. | VulnerabilityContract + graph revision. |
| **knowledge** | Case + graph | Truy xuất tài liệu/knowledge. | Retrieved context; không phải proof. |
| **skill_retrieval** | Graph/failure context + policy | Tìm FCSM, lọc operator. | Candidate skills và match reasons. |
| **poc_reasoning** | Contract + graph + source + skills | Chọn observable và action để kiểm tra edge chưa đạt. | SafePoCPlan typed. |
| **environment_plan** | Case + language template | Định nghĩa pair/build requirements. | DockerSpec typed. |
| **build_approval** | DockerSpec + provenance | Human review khi policy yêu cầu. | approved/rejected qua interrupt. |
| **build** | DockerSpec + pinned source | Dựng vulnerable/fixed pair, ghi digest/log. | ImageArtifacts. |
| **poc** | SafePoCPlan + validators | Compile/validate thành SafePoC IR. | safepoc.json với từ vựng hữu hạn. |
| **attempt_plan** | SafePoC + graph | attempt id, graph hash, pair, budget, expected results. | AttemptRecord immutable. |
| **execution_approval** | SafePoC + images + policy | Human review trước runtime. | approved/rejected. |
| **validate** | Image pair + PoC + test | Cùng plan trên hai roles, thu observation. | ValidationResult; simulation flag rõ. |
| **feedback** | Validation + graph | Classify failure, cập nhật graph qua evidence. | TypedFeedback + coverage + graph hash. |
| **skeptic** | Validation + coverage + reasoning | Áp dụng verdict predicate. | confirmed/candidate/rejected/not_executed. |
| **repair_reasoning** | Feedback + graph + FCSM | Xếp hạng repair được phép. | RepairDecision typed. |
| **repair** | Decision + allowlist | Sửa plan bằng SafePoC operators. | Plan mới, không tăng quyền. |
| **skill_update** | Outcome + evidence + control | Ghi application/update candidate status. | Application history. |
| **report** | Case artifacts | Tính proof bundle và render report. | Claims, missing gates, limitations. |
| **blocked** | Policy/input failure | Ghi nguyên nhân. | Report không xác nhận. |

Tên node theo scaffold hiện tại. Cần kiểm tra graph.py khi đổi route/approval behavior; docs không thay thế test control flow.

### 5.3 State, checkpoint, budget

ResearchState giữ case, phase/status, raw diff, source context, evidence, hypotheses, reasoning, Docker plan, SafePoC, validation, graph, attempts, feedback, skill và proof references. Giữ artifact lớn trong artifact store; state lưu metadata/path/hash. Dựng prompt từ state thô theo nhu cầu.

Scaffold compile graph với **InMemorySaver**: phù hợp demo/test cùng process nhưng không durable; restart có thể mất tiến trình chờ approval. Việc tiếp theo là checkpointer bền vững, state schema migration/versioning và interrupt/resume tests. Tham khảo [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview).

Mỗi case phải giới hạn thời gian tổng, provider calls/tokens, source query count, caller depth, candidate files, context bytes, build/run timeout, RAM/CPU/PID/disk, repair attempts và adapter actions. Hết budget thì report candidate; không tự nới policy.

## 6. Patch-complete, bidirectional source investigation

### 6.1 Luồng phân tích

1. Giữ raw diff và SHA-256.
2. Parse mọi file/hunk, old/new paths và line ranges.
3. Đối chiếu changed/context lines với hai snapshot.
4. Tìm function/method/class chứa thay đổi trong hai revision.
5. Lấy bounded source slices và index symbol/call sites.
6. Dựng caller graph ngược về entrypoint.
7. Dựng callee graph xuôi tới helper, parser, validation, sink candidate.
8. Cho model gọi query chỉ đọc sau khi thấy kết quả ban đầu.
9. Ghi revision, line range, parser/confidence và evidence IDs.
10. Đưa static relations vào reproduction graph dưới dạng hypothesized; chỉ runtime evidence hỗ trợ reachability.

### 6.2 Hai hướng slicing

| Hướng | Câu hỏi | Kết quả |
|---|---|---|
| **Backward callers** | Ai có thể gọi changed symbol? Có route, handler, test hoặc callback dẫn tới nó? | Call sites, caller paths, source locations, candidate entrypoints. |
| **Forward callees** | Hàm đã sửa gọi gì? Parser, deserializer, file/process operation hay validation nào ảnh hưởng transition? | Call sites, definitions, sink candidates, snippets. |

Đây là call relations, không phải control-flow proof. Framework routing, reflection, callback, aliasing, generated code và cross-language boundary có thể tạo false/missed edges.

### 6.3 Typed source tools

| Query | Tác dụng |
|---|---|
| **read_symbol** | Đọc body/metadata của function hoặc method candidate. |
| **find_callers** | Caller candidates và tùy chọn recursive paths. |
| **find_callees** | Call sites, definitions và tùy chọn recursive paths. |
| **read_test** | Đọc test từ revision đã pin. |

Query chỉ nhận role vulnerable/fixed, repository-relative path đã validate, depth và giới hạn kết quả. Không nhận Git ref bất kỳ, path ngoài allowlist, shell, Docker hoặc network action.

### 6.4 Parser và confidence

Python dùng standard AST. Một số ngôn ngữ khác dùng bounded structural scanner và relation được gắn candidate label. Mỗi relation giữ parser, revision, file, line/call-site, resolution class và hash. Static relation không đếm vào dynamic reachability.

Source context chỉ đủ khi parser accounting đầy đủ và hunk verify đúng snapshot. Nếu không, route candidate/report. Nâng cấp ưu tiên: parser theo ngôn ngữ, compiler-backed symbol resolution, framework route analysis, CodeQL/Semgrep adapters pin version, data-flow và runtime trace. Đo precision/recall; không chỉ đếm edge.

## 7. Agent reasoning và quyền công cụ

### 7.1 LLM được làm gì?

LLM có thể đọc raw patch đầy đủ và mapped source context; yêu cầu typed source queries; tạo hypotheses cạnh tranh có evidence IDs; giải thích patch có thể sửa điều kiện nào; nêu uncertainty/alternative/disconfirmation; chọn graph transition cần quan sát; đề xuất SafePoCPlan hoặc repair operator trong allowlist.

LLM không thể chạy terminal tùy ý, đọc path ngoài case, sửa source/revisions/policy, mở network, thêm DSL action, tự đánh dấu coverage/confirmed, hoặc lấy prose của nó làm runtime evidence.

### 7.2 Reasoning có thật, không giả lập bằng heuristic

Provider mặc định là **required**. OpenAI/Ollama được chọn tường minh. Thiếu provider thì không fallback ngầm sang heuristic. Heuristic chỉ cho offline tests và không thể xác nhận.

Reasoning record lưu provider/model, prompt version, input/output fingerprints, candidate hypotheses, evidence IDs, candidate được chọn, source tool calls, missing transitions, next bounded action, uncertainty và rationale ngắn. Không lưu hidden chain-of-thought.

### 7.3 Vì sao tách Docker khỏi LLM?

Có thể cấp cho agent terminal/container rộng quyền, nhưng khi đó khó kiểm chứng hành động nào tạo kết quả, khó giới hạn side effects và khó chạy lại đồng nhất trên fixed revision. Patch2Proof giữ năng lực reasoning ở model; capability thực thi ở typed plan, validator, adapter và worker. Đây là lựa chọn về provenance/kiểm soát của hệ thống, không phải khẳng định mọi agent paper đều cấm shell.

Patch, README và tool output có thể chứa prompt injection. Coi chúng là data; query registry tĩnh; validate evidence IDs; giới hạn output; kết luận vẫn cần oracle và skeptic.

## 8. Directed reproduction graph

### 8.1 Semantics

Mỗi case có DAG typed/versioned. Node biểu diễn patch hunk, symbol, entrypoint, precondition, runtime state, observation, artifact hoặc revision. Edge biểu diễn quan hệ như modifies, calls, flows_to, requires, reaches, transitions, observed_by, derived_from, supports, contradicts, absent_on_fixed.

~~~mermaid
flowchart TD
    A["Patch hunk"] --> B["Changed symbol"]
    C["Registered entrypoint"] --> D["Precondition"]
    D --> E["Changed slice reached"]
    E --> F["Semantic state transition"]
    F --> G["Bounded observable"]
    F --> H["Fixed or benign control"]
~~~

Patch-to-symbol có thể hỗ trợ bằng diff/source evidence. Runtime reachability/semantic transition cần adapter/oracle observation. Edge mới bắt đầu hypothesized/unobserved; chỉ evidence phù hợp mới hỗ trợ. Mỗi attempt lưu graph hash trước/sau; không sửa lịch sử.

### 8.2 Sáu coverage gates

Implementation hiện có sáu gate, trong khi một số module docs cũ ghi năm. Cần thống nhất schema, docs và tests theo bảng:

| Gate | Điều kiện |
|---|---|
| **static_reachability** | Hunk được map tới symbol và source evidence. |
| **dynamic_reachability** | Runtime trace/registered observation chứng minh entrypoint tới changed slice. |
| **semantic_transition** | Quan sát state transition bảo mật mục tiêu, không chỉ return code/crash. |
| **counterfactual_separation** | Cùng plan cho expected vulnerable result nhưng không tạo vulnerable signal trên fixed/benign. |
| **repeatable** | Paired result lặp lại cùng inputs/fixture/policy. |
| **source_grounded** | Claim/edge trỏ tới source/runtime evidence có provenance. |

Report cần evidence và lý do cho từng Boolean. Confidence của LLM không phải gate.

### 8.3 Planner và repair

Planner chọn edge chưa đạt theo policy, risk, cost và thông tin hiện có. Validator kiểm tra edge tồn tại, operator nằm trong allowlist, source/revision/fixture không đổi, attempt còn budget và không có permission expansion. Nếu observation mâu thuẫn hypothesis, ghi edge contradicts và đánh giá lại hypothesis; không chỉ sửa PoC.

## 9. SafePoC, oracle và ví dụ

### 9.1 DSL giới hạn

SafePoC hiện có các action: read_canary, write_marker, http_mock_request, assert_log, observe_exit, establish_fixture_state, invoke_entrypoint, observe_trace, assert_state và reset_environment.

Target phải nằm trong fixture, registered entrypoint, mock service hoặc proof artifacts. DSL không có generic exec/shell, download, connect IP tùy ý, đọc host file hoặc mount host. Compiler validate action, target, graph references, policy và expected observable trước execution.

### 9.2 Oracle

Validator ghi baseline/before/after/delta/expected/match cho mỗi role, cùng role id, image digest, plan hash và evidence IDs.

~~~text
pass =
  expected_vulnerable_observation(vulnerable_run)
  AND expected_fixed_observation(fixed_run)
  AND target_specific_difference(vulnerable_run, fixed_run)
  AND repeat_check
  AND no_policy_violation
~~~

Exit 0, crash, timeout hay log đơn lẻ không tự xác nhận. Oracle phải độc lập với câu trả lời LLM và được adapter đăng ký/review. “Độc lập” ở đây nghĩa verdict đến từ assertion/collector đã định nghĩa và runtime evidence, không bắt buộc phải là hệ thống bên thứ ba chạy process riêng.

### 9.3 Ví dụ khái niệm: deserialization dẫn tới tác động nguy hiểm

Ví dụ an toàn ở mức phân tích, không gồm gadget chain hay payload khai thác:

1. **Patch:** thêm check trước khi object graph được chấp nhận. Pipeline giữ diff và map hunk vào vulnerable/fixed implementation.
2. **Source investigation:** caller direction tìm handler/test entrypoint; callee direction đọc parser/decoder và callback. Static edges vẫn là candidates.
3. **Hypotheses:** model nêu input chưa được kiểm tra, check nằm sau object creation, hoặc behavior chỉ xảy ra với cấu hình nhất định. Mỗi hypothesis trỏ tới evidence và có phép thử phản chứng.
4. **Graph:** registered entrypoint → fixture precondition → changed slice reached → benign callback/state marker → fixed control.
5. **SafePoC:** adapter gọi harness đã đăng ký với fixture vô hại; oracle theo dõi marker/state trong container. Không gọi shell, process thật hay target bên ngoài.
6. **Pair:** cùng fixture bytes, setup và plan trên hai image. Hỗ trợ hypothesis nếu transition xuất hiện trên vulnerable nhưng bị chặn/không xuất hiện trên fixed.
7. **Repair:** nếu handler chưa tới thì reachability/harness failure; nếu handler chạy nhưng marker không có thì hypothesis/oracle failure. FCSM chỉ gợi ý setup/instrumentation khi operator được phép.
8. **Verdict:** thiếu trace, counterfactual hoặc repeatability thì candidate dù source reasoning hợp lý.

Agent có thể reproduce semantic property trong harness kín mà không cần quyền tạo hành vi gây hại.

## 10. Docker và execution plane

### 10.1 Cặp build

Vulnerable/fixed cần giống nhau ở base image digest, dependencies/lockfile, OS packages, environment, fixture, configuration, startup adapter và resource policy. Chỉ source revision đổi. Ghi commit SHA, diff hash, Dockerfile/template hash, base digest, lock hash, logs, image ids, worker version, policy và fixture/SafePoC hashes.

Mặc định network none. Nếu cần giao tiếp, chỉ dùng mock network đã khai báo. Git contexts qua adapter fixed-argument, model không tự cung cấp Git command.

### 10.2 Runtime policy mục tiêu

Worker riêng trong disposable VM/rootless boundary; network none/mock-only; read-only rootfs; drop capabilities; no-new-privileges; không Docker socket/host credentials; chỉ scoped artifact directory; quota CPU/RAM/PID/time/disk/output; cleanup sau run.

### 10.3 Trạng thái thực tế

Scaffold có Docker planning/worker contract và simulated adapter cho tests. Simulated adapter luôn đánh dấu simulation và không thể tạo confirmed.

**Gap quan trọng:** worker hiện gọi Docker CLI từ cùng process. Spec hạn chế chưa đồng nghĩa với hardened isolation boundary. Trước case rủi ro cao, chuyển execution sang rootless worker/VM riêng và kiểm thử egress/filesystem/resource/cleanup policy. Không mô tả isolation như đã được chứng minh.

## 11. Failure-Conditioned Skill Memory (FCSM)

### 11.1 Vai trò

FCSM lưu strategy thao tác an toàn, không phải exploit memory/oracle. Ví dụ: “khởi tạo fixture trước registered entrypoint” hoặc “thêm trace observer tại source-aligned transition”. Entry nên giữ language/framework/build, vulnerability class, failure class, missing transition, observable, allowed operators, expected transitions, forbidden effects, status, provenance và application history.

### 11.2 Retrieval

~~~text
failure class
→ missing graph transition
→ intersection với allowed repair operators
→ language/framework/build/vulnerability metadata
→ historical verified cost and outcome
~~~

Candidate thiếu operator intersection bị loại. Nếu thêm embedding, nó chỉ xếp hạng trong tập đã lọc, không vượt policy.

### 11.3 Application và promotion

Mỗi lần áp dụng ghi skill id, case/attempt, transitions gained, evidence IDs, outcome và fixed-control status. Failure không tự tạo capability mới. Prototype JSON hiện dùng rule: validated sau một verified application; promoted sau hai paired counterfactual applications.

Để tăng độ tin cậy: định nghĩa verified application bằng oracle; reviewer labels/signed approvals; split theo case family để tránh leakage; retirement khi regression; đánh giá với no-memory, generic RAG và rule baseline. Đo retrieval precision@k, repeated failures, attempts/time/cost tới coverage, held-out transfer và regression. Không lưu target-specific payload hay secret.

## 12. Evidence, DACN và report

### 12.1 Hợp đồng dữ liệu

| Contract | Vai trò |
|---|---|
| **CaseManifest** | Scope, revisions, language/build, adapter, policy, budgets. |
| **Evidence** | Observation + provenance/hash/location/revision. |
| **Hypothesis** | Explanation khả dĩ, preconditions, affected path, observable, evidence IDs. |
| **AgentReasoning** | Alternatives, uncertainty, missing transitions, next bounded action. |
| **SourceContextBundle** | Hunk mapping, symbols, slices, callers/callees, parser coverage. |
| **VulnerabilityContract** | Preconditions và expected vulnerable/fixed transition. |
| **ReproductionGraph** | Nodes/edges, status, evidence, revision, hash. |
| **SafePoCPlan/SafePoC** | Model plan và IR đã validate. |
| **TypedFeedback** | FailureClass, missing transition, observations, allowed repairs. |
| **AttemptRecord** | Attempt id, parent, plan/graph hashes, status, evidence. |
| **ValidationResult** | Pair observations, differential, oracle, simulation, violations. |
| **SkillApplication** | Strategy dùng và outcome. |
| **ProofBundle** | Predicate, claims, missing gates, artifact hashes. |

DACN-compatible substrate giữ source/vulnerability/environment/build/execution/verification và immutable artifacts. Patch2Proof thêm agent overlay: reasoning, graph, feedback, skill application và proof eligibility. Tích hợp thật nên lưu overlay thành child records, không ghi đè records gốc.

### 12.2 Artifact layout

~~~text
artifacts/<case-id>/
  case.json
  raw-patch.diff
  source-identities.json
  patch-analysis.json
  source-context.json
  reasoning/
  vulnerability-contract.json
  reproduction-graph.json
  coverage.json
  docker-plan.json
  builds/
  safepoc-plan.json
  safepoc.json
  attempts/
  validation.json
  feedback/
  skeptic-review.json
  skill-memory-summary.json
  proof-bundle.json
  final-report.md
  manifest.json
~~~

Manifest lưu path, content hash, type, revision, producer node, timestamp, parent artifact ids, prompt/model version và simulation flag. Không ghi đè attempt cũ; tạo artifact mới có parent reference.

### 12.3 Report cuối

Báo cáo gồm verdict/giới hạn claim; case provenance/revisions/patch hash; root-cause hypothesis; hunk-to-symbol và caller/callee evidence; entrypoint/preconditions/trust boundary; image/build digests; SafePoC/adapter; vulnerable/fixed observations; graph/coverage; attempts/feedback/FCSM; proof predicate/missing evidence; impact/CWE/CVSS rationale nếu đủ cơ sở; remediation; safety/limitations/reproduction steps.

Dùng ngôn ngữ có ranh giới: “Diff thay đổi…” cho observation trực tiếp; “Điều này gợi ý…” cho inference; “Vulnerable image quan sát…” cho runtime; “Fixed image không quan sát…” cho control. Không gọi confirmed chỉ vì LLM tạo input hoặc vulnerable run crash.

### 12.4 Proof predicate

Proof bundle tính bằng code xác định, độc lập với prose:

~~~text
confirmed =
  exact vulnerable/fixed identities
  AND same fixture and SafePoC bytes on both roles
  AND independent oracle match
  AND target-specific differential
  AND static_reachability
  AND dynamic_reachability
  AND semantic_transition
  AND counterfactual_separation
  AND repeatable
  AND source_grounded
  AND non-simulated adapter
  AND provider-backed reasoning artifact
  AND no policy violation
~~~

Thiếu điều kiện thì candidate/blocked/not_executed theo precedence đã định; nêu gate thiếu. Model không override.

## 13. Scaffold, giới hạn và việc cần làm

### 13.1 Đã có

- LangGraph workflow cho preflight, ingest, patch/source analysis, reasoning, graph, planning, approvals, paired validation, feedback, skeptic, repair, skill update, report.
- Provider-backed OpenAI/Ollama, fail-closed default, heuristic explicit test-only.
- Raw patch đầy đủ; revision-aware hunk verification; Python AST và structural candidates; read-only source queries.
- Typed contracts; directed graph; coverage; FCSM JSON prototype; SafePoC vocabulary; Docker planning/adapter; proof bundle/report.
- Simulated adapter bị chặn khỏi confirmed.
- DACN reference subtree/schema examples.

### 13.2 Gaps

| Gap | Tác động | Ưu tiên |
|---|---|---|
| InMemorySaver | Không resume bền vững sau restart/approval wait. | Cao |
| Docker CLI cùng process | Chưa là hardened isolation boundary. | Rất cao trước case thật |
| Call graph là static candidates | Có false/missed callers; không chứng minh reachability. | Cao |
| Structural parser ngoài Python | Chất lượng chưa tương đương compiler/parser. | Cao |
| Thiếu non-simulated adapters | Scaffold pass không đồng nghĩa real reproduction. | Cao |
| Một số docs ghi 5 gates, implementation 6 | Schema/evaluation có thể lệch. | Cao |
| FCSM promotion thiếu reviewer/provenance | Transfer có thể bị overclaim. | Trung bình-cao |
| Chưa có benchmark hoàn chỉnh | Chưa thể claim efficacy. | Cao |
| Worker provenance/signature chưa hoàn chỉnh | Khó xác minh runtime source. | Trung bình |
| Risk score/CVSS dễ tạo false precision | Cần human review và rationale. | Trung bình |

### 13.3 Nguyên tắc không làm yếu

Không bật heuristic fallback; không raw shell/Docker flags từ LLM; không tính simulation là validation; không dùng static edge làm dynamic reachability; không bỏ fixed counterfactual; không promotion FCSM chỉ bằng rationale; không gộp candidate/confirmed; không chạy ngoài authorization/lab.

## 14. Evaluation protocol

### 14.1 Dataset

Bắt đầu 6–10 case tái lập hợp pháp, mở rộng 20–30 nếu adapter/reviewer capacity cho phép. Mỗi case cần advisory/patch, exact revisions, source provenance, deterministic build, registered harness, safe semantic oracle, negative fixture/fixed control, policy và resource budget.

Cân bằng language/build/vulnerability family/độ phức tạp. Deserialization, command/process, SSRF hoặc RCE chỉ trong harness local được review; ưu tiên marker/canary/mock trace.

### 14.2 Baselines và ablations

Dùng cùng model, budget, case, pair, adapter và proof predicate:

1. Diff-only reasoning.
2. Complete patch + changed-symbol mapping.
3. Complete patch + bidirectional call candidates.
4. Tool-using investigator + reproduction graph.
5. Full system không FCSM.
6. Full system không execution feedback.
7. Vulnerable-only/weak oracle chỉ như negative comparison.
8. Heuristic explicit test baseline, báo riêng.
9. Human-created plan làm reference khi capacity cho phép.

Bỏ fixed counterfactual chỉ để đo false positives; production verdict vẫn dùng paired predicate.

### 14.3 Metrics

- **Localization:** hunk-to-symbol, affected path top-k, caller/callee precision/recall theo depth.
- **Reasoning:** citation precision, unsupported hypothesis, calibration, missing-transition prediction.
- **Plan:** SafePoC acceptance/rejection, compiler failure, oracle specificity.
- **Execution:** build rate, differential pass, repeatability, resource failures.
- **Proof:** confirmation precision, false confirmation, evidence completeness/source grounding.
- **Efficiency:** attempts, median/p90 time, tokens/cost, source queries, time tới accepted graph.
- **FCSM:** retrieval precision@k, repeated failure reduction, held-out transfer, regression.
- **Safety:** forbidden effects, policy-block accuracy, host/egress violation; target violation = 0.
- **Human:** reviewer agreement, review time, ambiguity.

Báo cáo failures; paired case stats và confidence intervals khi đủ sample. Split theo project/family để tránh leakage prompt/memory/test.

### 14.4 Failure taxonomy

Tách metadata/revision; dependency/toolchain/build; startup/config/harness; source mapping/localization; reachability; hypothesis; SafePoC planning/compiler; oracle ambiguity; fixed-control failure; resource exhaustion; policy block; simulation/unsupported adapter. Không gộp mọi lỗi thành “agent thất bại”.

## 15. Lộ trình phát triển

### Phase A — Tái lập scaffold
Cài, chạy tests/dry-run, kiểm tra artifacts/routing/provider fail-closed, thống nhất sáu gates, ghi dependency/model/prompt versions. **Exit:** người mới chạy demo và phân biệt simulation.

### Phase B — Adapter local thật, rủi ro thấp
Chọn Python case, harness/canary oracle, ghim revisions/lockfile/base digest, chạy cùng PoC trên pair, reviewer duyệt. **Exit:** ít nhất một non-simulated case đủ evidence hoặc report chính xác gate thiếu.

### Phase C — Durable graph và worker boundary
Durable checkpointer, worker VM/rootless riêng, interrupt/resume tests, network/fs/resource tests, cleanup, artifact manifest. **Exit:** restart/resume tái lập; worker policy test độc lập.

### Phase D — Source-analysis quality
Labeled call-path dataset, parser/compiler-backed resolution, framework routes, runtime trace/source mapping, metrics theo depth. **Exit:** held-out precision/recall.

### Phase E — FCSM
Reviewer labels, lifecycle audit, held-out family, no-memory/RAG/rule baselines, negative transfer/retirement analysis. **Exit:** memory giảm lặp failure mà không tăng false confirmation/violations.

### Phase F — Benchmark và luận án
Mở rộng cases theo năng lực; freeze prompt/policy/splits; paired ablations/review; publish scripts, hashes, limitations và raw tables; claim hẹp đúng evidence.

