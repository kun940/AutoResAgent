SAMPLE_COMPLAINTS = {
    "A_missing_parts": {
        "text": "我的订单JD9988776655，Pro-Max-V2型号，缺少螺丝包，批次X11",
        "expected": {
            "order_id": "JD9988776655",
            "model_number": "Pro-Max-V2",
            "batch_code": "X11",
            "urgency_level": "Low_Priority",
            "issue_category": "Missing_Parts",
            "routing_decision": "frontline_staff_queue",
            "auto_reply_keywords": ["补发", "配送", "寄送"],
        }
    },
    "B_smoke": {
        "text": "Pro-Max-V2设备冒烟，订单JD9988776655",
        "expected": {
            "core_fault_desc_contains": "冒烟",
            "urgency_level": "High_Priority",
            "issue_category": "Hardware_Thermal_Runaway",
            "routing_decision": "general_manager_dashboard",
            "auto_reply_keywords": ["切断电源", "安全", "紧急"],
        }
    },
    "C_reboot": {
        "text": "核心部件频繁重启，订单JD5566778899",
        "expected": {
            "urgency_level": "Medium_Priority",
            "routing_decision": "department_manager_queue",
            "auto_reply_keywords": ["排查", "诊断", "重启"],
        }
    },
    "D_incomplete": {
        "text": "坏了",
        "expected": {
            "urgency_level": "Medium_Priority",
            "auto_reply_keywords": ["补充", "信息", "联系"],
        }
    },
}
