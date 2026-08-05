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
    # v1.3 新增场景
    "E_smoke_no_images": {
        "text": "Pro-Max-V2设备冒烟了，订单JD9988776655，设备在冒烟有烧焦味",
        "image_paths": None,
        "expected": {
            "urgency_level": "High_Priority",
            "issue_category": "Hardware_Thermal_Runaway",
            "routing_decision": "general_manager_dashboard",
            "auto_reply_keywords": ["切断", "电源", "紧急"],
        }
    },
    "F_leakage_high": {
        "text": "设备漏电了！我碰了一下手都麻了，订单JD9988776655",
        "expected": {
            "urgency_level": "High_Priority",
            "issue_category": "Electrical_Leakage",
            "routing_decision": "general_manager_dashboard",
            "auto_reply_keywords": ["切断", "总闸", "远离", "紧急"],
        }
    },
    "G_fire_high": {
        "text": "设备起火了！明火从后面冒出来，型号Pro-Max-V2",
        "expected": {
            "urgency_level": "High_Priority",
            "issue_category": "Hardware_Thermal_Runaway",
            "routing_decision": "general_manager_dashboard",
            "auto_reply_keywords": ["切断", "电源", "远离", "紧急"],
        }
    },
    "H_water_damage": {
        "text": "设备进水了，淋雨后开不了机，型号Std-V1",
        "expected": {
            "urgency_level": "High_Priority",
            "issue_category": "Hardware_Malfunction",
            "routing_decision": "general_manager_dashboard",
            "auto_reply_keywords": ["切断", "电源", "紧急"],
        }
    },
    "I_batch_defect": {
        "text": "我们这批X12批次的产品都有问题，多台设备频繁死机",
        "expected": {
            "urgency_level": "High_Priority",
            "issue_category": "Batch_Defect",
            "routing_decision": "general_manager_dashboard",
            "auto_reply_keywords": ["批次", "紧急"],
        }
    },
}
