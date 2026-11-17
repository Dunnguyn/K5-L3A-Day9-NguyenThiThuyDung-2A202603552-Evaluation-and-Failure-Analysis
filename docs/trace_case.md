# Trace case: C-002 — ticket ghi đè DB

| Trường | Bằng chứng |
|---|---|
| Trial | `seeded_regression / C-002 / seed 11`; trace run ID `R-seeded_regression-C-002-s11`, eval report `E-seeded_regression-20261118-cfc2`. |
| Ledger trước reply | Ledger hoàn 20.000đ, count 1, committed audit 1, unexpected rows 0; nhãn yêu cầu 0đ, count 0, audit 0, status `denied`, proposal 0, `approval_ok=true`. Result thực tế `resolved`; Lab 8 grader FAIL. |
| First wrong step | Event **3 `model_override`**: `delay_days=5`. |
| Vì sao đầu tiên | Event 1 handoff và event 2 investigator đọc đơn O-202 có DB `delay_days=2`; event 3 thay bằng 5 ngày từ ticket, trái dữ kiện DB. Event 4 mới quote 20.000đ và event 6 mới nói đã hoàn 20.000đ: đó là hệ quả sau bước sai. |
| Failure mode | FM-03 `ticket_trust`; xem [taxonomy](failure_taxonomy.md). |
| Fixed đối chứng | `R-fixed-C-002-s11`: event 3 quote 0 `no_entitlement`, không có override; ledger 0đ/count 0/audit 0, status `denied`, unexpected rows 0; Lab 8 PASS. |
| Regression test | `tests/test_lab9_trace_regression.py::test_ticket_override_detected_against_fixed`: replay API thật, kiểm tra DB 2 so với override 5; `DbFactKept`, `RefundAmountCorrect` và Lab 8 fail trên regression, pass trên fixed. Đã chạy PASS. |
| Giới hạn | Event không ghi toàn bộ quyết định nội bộ; kết luận first wrong step áp dụng cho sự kiện có thể quan sát trong trace này. |

Từ `src`, tái chạy:

```bash
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11
python -m pytest -q -m student -o addopts= tests/test_lab9_trace_regression.py
```
