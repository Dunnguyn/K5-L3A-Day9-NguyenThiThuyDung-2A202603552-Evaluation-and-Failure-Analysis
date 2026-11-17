# Judge audit

Hai bộ CSV công khai có 100 dòng mỗi bộ; lớp dương là **FAIL**, human là nhãn tham chiếu. Calibration dùng verdict replay, không gọi mô hình mới. Tỷ lệ hiệu chỉnh Rogan–Gladen dùng recall làm sensitivity và TN/(TN+FP) làm specificity trên chính tập này.

| Tiêu chí | TP | FP | FN | TN | Precision | Recall | κ | Fail quan sát | Fail hiệu chỉnh | Kết quả |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| tone_ok | 24 | 4 | 6 | 66 | 0,857 | 0,800 | 0,757 | 0,280 | 0,300 | PASS, exit 0 |
| helpful | 9 | 0 | 21 | 70 | 1,000 | 0,300 | 0,375 | 0,090 | 0,300 | FAIL, exit 1 |

Ngưỡng: κ ≥ 0,6, precision ≥ 0,8, recall ≥ 0,7. Số hiệu chỉnh là ước tính phụ thuộc sensitivity/specificity và độ phù hợp của nhãn; không phải số đo độc lập.

## Audit bất đồng

Nhận định dựa trên reply và cột `note`/`human_failure` trong CSV; các nguyên nhân là giả thuyết theo ghi chú, không phải giải thích nội bộ đã xác minh của judge.

| Item | Human | Judge | Reply liên quan | Đánh giá và căn cứ | Nguyên nhân có thể | Sửa rubric hoặc cách chấm |
|---|---|---|---|---|---|---|
| H-008 | FAIL | PASS | “Em đã hoàn tiền cho anh rồi nha, anh check giúp em.” | Theo ghi chú CSV, human đúng theo chuẩn giao tiếp vì cách xưng hô và “nha” quá suồng sã. | Judge coi thân thiện là đủ lịch sự. | Thêm ví dụ phân biệt thân thiện với suồng sã. |
| H-029 | FAIL | PASS | “Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm.” | Theo ghi chú, human đúng: vế cuối có giọng ra lệnh. | Có thể judge chỉ chú ý lời mở đầu lịch sự. | Chấm toàn bộ câu, nêu ví dụ yêu cầu mang tính áp đặt. |
| H-042 | PASS | FAIL | “Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ.” | Theo ghi chú, human đúng: ngắn nhưng đủ ý, không bắt buộc xin lỗi trong mọi trường hợp. | Có thể judge áp quy tắc xin lỗi quá rộng. | Chỉ yêu cầu xin lỗi khi ngữ cảnh hoặc rubric quy định. |
| H-051 | PASS | FAIL | “Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ.” | Theo ghi chú, human đúng vì chính sách CS cho phép “refund”. | Judge có thể phạt từ tiếng Anh. | Ghi rõ từ được phép và ví dụ song ngữ. |
| H-081 | PASS | FAIL | “Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ.” | Ghi chú CSV nói nhãn human sai do đọc nhầm ticket và judge đúng; CSV không cung cấp ticket nên chưa xác minh độc lập. | Ghi chú quy lỗi cho việc đọc nhầm ticket. | Kiểm tra ticket gốc và adjudicate trước khi sửa nhãn hoặc tính lại calibration. |
| HL-015 | FAIL | PASS | “Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ.” | Human đúng **nếu** ghi chú CSV “ledger ghi 40.000đ” chính xác; CSV không kèm ledger gốc. | Judge có thể dựa vào lời văn mà không đối chiếu ledger. | Xác minh ledger; dùng assertion code so sánh số tiền reply với ledger. |
| HL-020 | FAIL | PASS | “Dạ, LogiX đã hoàn 90.000đ cho đơn O-303 ạ.” | Human đúng **nếu** ghi chú “ledger ghi 120.000đ” chính xác; cần ledger gốc để xác minh. | Có thể judge bỏ qua tính đúng của số tiền. | Dùng grader code đối chiếu ledger thay vì chỉ đánh giá văn phong. |

## Kết luận và giới hạn

`tone_ok` vượt cả ba ngưỡng trên bộ replay công khai, nên có thể dùng làm judge cho tone theo calibration này, với giám sát các bất đồng và kiểm tra lại trên dữ liệu độc lập trước khi mở rộng sử dụng. Việc vượt ngưỡng không chứng minh judge đúng ở mọi ngữ cảnh; H-081 còn cần adjudication nhãn.

`helpful` không được dùng làm blocking judge theo kết quả này: 21 FN trong 30 lỗi do human gán khiến recall chỉ 0,300 và κ 0,375, dù precision là 1,000. Sai số tiền nên được chấm bằng code dựa trên ledger, không giao cho judge văn phong.

Đây là calibration trên dữ liệu replay công khai, không phải tập held-out độc lập; không có độ tin cậy thống kê hay chứng cứ tổng quát hóa sang dữ liệu mới. Cần thu thập nhãn người mới, ledger/ticket gốc, adjudicate các nhãn tranh chấp và đánh giá lại trên tập giữ riêng.
