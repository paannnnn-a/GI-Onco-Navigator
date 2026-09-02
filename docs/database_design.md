# Database Design

## Overview

GI-Onco Navigator uses structured data models to represent:

- Patient information
- Cancer diagnosis
- Treatment status
- Medical knowledge
- Expert video resources


---

# 1. Patient Table

Store basic patient information.

| Field | Type | Description |
|-|-|-|
| patient_id | String | Unique identifier |
| age | Integer | Patient age |
| gender | String | Gender |
| province | String | Location |
| cross_province | Boolean | Accept cross-province treatment |


Example:

```json
{
 "patient_id":"P001",
 "age":65,
 "gender":"male",
 "province":"Shandong",
 "cross_province":false
}
