```
  "defaults": {
    "subject_per_session": number,             // Số môn tối đa trong một buổi
    "subject_per_day": number,                 // Số môn tối đa trong một ngày
    "duration_of_session": {                   // Giới hạn tối đa hoặc tối thiểu số tiết học
      "value": number,                         // Số tiết học của môn học (ví dụ: 2)
      "up_or_down": "up" | "down",             // up | down: muốn học `value` tiết trở lên/ trở xuống
      "like": boolean
    },
    "period": {                                 // Muốn / tránh học từ tiết mấy đến tiết mấy
      "value": [2, 3, 4, 5, 6, 7],
      "like": true
    },
    "period_onward": {
      "value": number,                         // Tiết học bắt đầu ưu tiên (ví dụ: 3)
      "like": boolean
    },
    "hour_onward": {
      "value": number,                         // Giờ bắt đầu ưu tiên (ví dụ: 9)
      "unit": "hour",
      "like": boolean
    },
    "area": {
      "value": string,                         // Khu vực học mong muốn (ví dụ: "K")
      "like": boolean
    },
    "room": [                                  // Danh sách phòng học mong muốn hoặc cần tránh
      { "value": string, "like": boolean }
    ],
    "class": [                                 
      {
        "name": string,                           // Tên môn học
        "class_group": [                          // Tên lớp học phần muốn học hoặc tránh
          { "value": number, "like": boolean }
        ],
        "teacher": [                               // Danh sách giáo viên muốn học hoặc tránh
          { "name": string, "like": boolean }
        ],
      }
    ],
    "rest_interval": {
      "value": number,                         // Số tiết nghỉ giữa các môn (ví dụ: 1)
      "up_or_down": "up" | "down",             // Giới hạn tối đa hoặc tối thiểu thời gian nghỉ
      "like": boolean
    }
  },
  "periods": [                                  // Các ràng buộc cụ thể theo từng ngày
    {
      "day": 
        { "value": string, "like": boolean } // Tên ngày trong tuần, ví dụ: "Thứ 2"
      ,  
      "period": { "value": [number], "like": boolean }, // Các tiết học muốn học trong ngày
      "subject_count": { "value": number, "like": boolean }, // Số môn muốn học hôm đó
      "duration_of_session": {                   
        "value": number,                         
        "up_or_down": "up" | "down",             
        "like": boolean
      },
      "rest_interval": {                                // Số tiết nghỉ giữa các môn (ví dụ: 1)
        "value": number,
        "up_or_down": "up" | "down",
        "like": boolean
      },
      "teacher": [ { "name": string, "like": boolean } ],
      "room": [ { "value": string, "like": boolean } ],
      "area": { "value": string, "like": boolean },
      "class": [
        {
          "name": string,
          "class_group": [
            { "value": number, "like": boolean }
          ]
        }
      ],
      "period_onward": {
        "value": number,
        "like": boolean
      },
      "hour_onward": {
        "value": number,
        "unit": "hour",
        "like": boolean
      }
    }
  ]
```

Gợi ý thêm:  
- ```"like"```: true nghĩa là ưu tiên, ```"like"```: false là tránh.
- ```Buổi sáng```: tiết 1 đến tiết 5, ```Buổi chiều```:  tiết 6 đến tiết 9, ```Cả ngày```: tiết 1 đến tiết 9
- Sáng: ```Tiết 1: 07h30```, ```Tiết 2: 08h30```, ```Tiết 3: 09h30```, ```Tiết 4: 10h30```, ```Tiết 5: 11h30```, Chiều: ```Tiết 6: 13h00```, ```Tiết 7: 14h00```, ```Tiết 8: 15h00```, ```Tiết 9: 16h00```, ```Tiết 10: 17h00"```
- Tách area và room như này: ```V.A201 thì trước dấu chấm là area, toàn bộ sau dấu chấm là room```

Lưu ý:
- Nếu không có yêu cầu cụ thể thì không cần đưa vào `periods`, chỉ đưa vào `defaults`.
- Nếu những yêu cầu đưa vào `periods`, thì không cần đưa vào `defaults` nữa
- Nếu không có thông tin nào về  field là mảng được đề cập từ người dùng thì hãy để mảng rỗng
- Nếu không có thông tin nào về  field là object được đề cập từ người dùng thì hãy để object đó là null


Ví dụ:

```
{
  "defaults": {
    "subject_per_session": 1,
    "subject_per_day": 3,
    "duration_of_session": {
      "value": 2,
      "up_or_down": "down",
      "like": true
    },
    "period": {
      "value": [2, 3, 4, 5, 6, 7],
      "like": true
    },
    "period_onward": {
      "value": 3,
      "like": true
    },
    "hour_onward": {
      "value": 9,
      "unit": "hour",
      "like": true
    },
    "area": {
      "value": "K",
      "like": true
    },
    "room": [
      { "value": "A101", "like": true },
      { "value": "A102", "like": true }
    ],
    "class": [
      {
        "name": "Automat và ngôn ngữ hình thức",
        "class_group": [],
        "teacher": [
            { "name": "Mai Lam", "like": true },
            { "name": "Tuấn", "like": false }
        ]
      },
      {
        "name": "",
        "class_group": [],
        "teacher": [
            { "name": "Phượng", "like": true },
            { "name": "Trọng", "like": true }
        ]
      }
    ],
    "rest_interval": {
        "value": 1,
        "up_or_down": "down",
        "like": true
    }
  },
  "periods": [
    {
      "day":
        {"value":  "Thứ 2", "like":  true}
      ,
      "period": {"value":  [6, 7, 8, 9], "like":  true},
      "subject_count": {"value":  1, "like":  true},
      "duration_of_session": {
        "value": 3,
        "up_or_down": "up",
        "like": true
      },
      "rest_interval": {
        "value": 1,
        "up_or_down": "down",
        "like": true
      },
      "room": [
        { "value": "A101", "like": true }
      ],
      "area": {
        "value": "K",
        "like": true
      },
      "class": [
        {
          "name": "Tiếng anh nâng cao 4",
          "class_group": [
            {"value":  2, "like":  true},
            {"value":  4, "like":  true}
          ],
          "teacher": [
            { "name": "Kim Tuyến", "like": true }
          ]
        }
      ],
      "period_onward": {
        "value": 8,
        "like": true
      },
      "hour_onward": {
        "value": 15,
        "unit": "hour",
        "like": true
      }
    },
    {
      "day":
        {"value":  "Thứ 4", "like":  true}
      ,
      "period": {"value":  [1, 2, 3, 4], "like":  true},
      "subject_count": {"value":  2, "like":  true},
      "duration_of_session": null,
      "rest_interval": {
        "value": 1,
        "up_or_down": "down",
        "like": true
      },
      "room": [
        { "value": "A101", "like": false }
      ],
      "class": [
        {
          "name": "Triết học Mac-Lenin",
          "class_group": [
            {"value":  2, "like":  true},
            {"value":  4, "like":  true}
          ],
          "teacher": [
            { "name": "Phượng", "like": true }
          ]
        }
      ],
      "period_onward": null,
      "hour_onward": null,
      "area": {
        "value": "K",
        "like": true
      }
    }
  ]
}
```
