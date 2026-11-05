"""Reading the metadata clients already have: Power BI models, dbt files and
data dictionaries."""

from __future__ import annotations

import json

import pytest

from ontology import metadata as md

BIM = {"name": "Finance", "compatibilityLevel": 1550, "model": {
    "tables": [
        {"name": "DimCustomer", "description": "Every customer we bill.", "columns": [
            {"name": "CustomerKey", "dataType": "int64", "sourceColumn": "CustomerKey"},
            {"name": "Customer Name", "dataType": "string", "description": "Legal name",
             "sourceColumn": "cust_name"},
            {"name": "RowNumber-2662979B", "type": "rowNumber", "dataType": "int64"}]},
        {"name": "FactSales", "columns": [
            {"name": "CustomerKey", "dataType": "int64"},
            {"name": "SalesAmount", "dataType": "decimal", "description": "Net sales",
             "formatString": "\\$#,0.00"},
            {"name": "OrderDate", "dataType": "dateTime"}],
         "measures": [{"name": "Total Sales", "expression": "SUM(FactSales[SalesAmount])",
                       "description": "All net sales"}]},
        {"name": "LocalDateTable_123", "isHidden": True, "columns": []}],
    "relationships": [{"name": "r1", "fromTable": "FactSales", "fromColumn": "CustomerKey",
                       "toTable": "DimCustomer", "toColumn": "CustomerKey"}]}}


def test_power_bi_model(tmp_path):
    path = tmp_path / "model.bim"
    path.write_text(json.dumps(BIM), encoding="utf-8")
    meta = md.parse(path)
    assert meta["kind"] == "powerbi"
    assert set(meta["tables"]) == {"DimCustomer", "FactSales"}
    cust = meta["tables"]["DimCustomer"]
    assert cust["description"] == "Every customer we bill."
    assert "RowNumber-2662979B" not in cust["columns"]
    assert cust["columns"]["Customer Name"]["description"] == "Legal name"
    assert meta["measures"][0]["expression"] == "SUM(FactSales[SalesAmount])"
    assert meta["relationships"][0]["to_table"] == "DimCustomer"
    # The model's display name or its source column both match a loaded column.
    assert md.column_info(meta, "customer", "cust_name")["description"] == "Legal name"
    assert md.column_info(meta, "fact_sales", "salesamount")["description"] == "Net sales"


def test_dbt_schema_with_relationship_tests_and_semantic_models(tmp_path):
    path = tmp_path / "schema.yml"
    path.write_text("""
version: 2
models:
  - name: stg_orders
    description: One row per order.
    columns:
      - name: order_id
        description: Primary key.
      - name: customer_id
        description: The buyer.
        data_tests:
          - not_null
          - relationships:
              to: ref('stg_customers')
              field: id
        meta: {label: Customer, unit: ""}
semantic_models:
  - name: orders
    model: ref('stg_orders')
    measures:
      - name: order_total
        agg: sum
        expr: amount
""", encoding="utf-8")
    meta = md.parse(path)
    assert meta["kind"] == "dbt"
    assert meta["tables"]["stg_orders"]["description"] == "One row per order."
    assert meta["tables"]["stg_orders"]["columns"]["customer_id"]["label"] == "Customer"
    assert meta["relationships"] == [{"from_table": "stg_orders", "from_column": "customer_id",
                                      "to_table": "stg_customers", "to_column": "id",
                                      "active": True}]
    assert meta["measures"][0]["expression"] == "sum(amount)"
    assert md.match_table(meta, "orders") is meta["tables"]["stg_orders"]


def test_data_dictionary_with_flexible_headers(tmp_path):
    path = tmp_path / "dict.csv"
    path.write_text("Table Name,Field,Business Definition,Business Name,UOM\n"
                    "KNA1,KUNNR,Customer number,Customer,\n"
                    "VBAK,NETWR,Net value of the order,Net value,EUR\n"
                    ",MANDT,SAP client,,\n", encoding="utf-8")
    meta = md.parse(path)
    assert meta["kind"] == "dictionary"
    netwr = md.column_info(meta, "vbak", "netwr")
    assert netwr == {"description": "Net value of the order", "label": "Net value",
                     "unit": "EUR", "type": ""}
    assert md.column_info(meta, "anything", "mandt")["description"] == "SAP client"
    assert md.column_info(meta, "kna1", "nope") is None


@pytest.mark.parametrize("name,content,error", [
    ("x.json", "{\"a\": 1}", "not a semantic model"),
    ("x.json", "{oops", "not valid JSON"),
    ("x.yml", "foo: bar", "not a dbt file"),
    ("x.csv", "a,b\n1,2\n", "needs a 'column' column"),
    ("x.txt", "hello", "give a Power BI model"),
])
def test_unreadable_files_explain_themselves(tmp_path, name, content, error):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    with pytest.raises(md.MetadataError, match=error):
        md.parse(path)


def test_missing_file_and_folder_of_files(tmp_path):
    with pytest.raises(md.MetadataError, match="not found"):
        md.parse(tmp_path / "nope.bim")
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "model.bim").write_text(json.dumps(BIM), encoding="utf-8")
    (tmp_path / "m" / "d.csv").write_text("column,description\nCustomerKey,The key\n",
                                          encoding="utf-8")
    meta = md.parse(tmp_path / "m")
    assert meta["kind"] == "mixed" and "FactSales" in meta["tables"]
    assert md.column_info(meta, "whatever", "customerkey")["description"] == "The key"


def test_names_compare_like_a_person_would():
    assert md.norm("dim_Customer") == md.norm("CUSTOMER") == "customer"
    assert md.norm("sales.FactSales") == "sales"
    assert md.norm("Factory") == "factory"
    assert md.norm("fact_sales") == "sales"
    assert md.norm("Customer Name") == "customername"
