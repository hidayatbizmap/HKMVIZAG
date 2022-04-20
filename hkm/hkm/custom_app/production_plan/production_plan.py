import frappe
from frappe.model.mapper import get_mapped_doc
from erpnext.manufacturing.doctype.bom.bom import get_bom_items
import collections
import json
from frappe import msgprint, _

# from erpnext.manufacturing.doctype.production_plan.production_plan import get_bin_details
# from erpnext.manufacturing.doctype.production_plan.production_plan import get_items_for_material_requests

@frappe.whitelist()
def make_stock_entryfg(source_name, target_doc=None):

    def set_missing_values(source, target):
        target.stock_entry_type = "Manufacture"
        # print("////source", source, type(source), source.__dict__)
        # s_doc = source.__dict__
        # print("////source", source, type(source))
        # data = get_items_for_material_requests(source)
        # print("/////s_doc",source,source.po_items, source.get('po_items') )
        # print("@@@@@",[s.sales_order for s in source.sales_orders])
        so_items = frappe.db.get_list("Sales Order Item", {'parent': ["in", [s.sales_order for s in source.sales_orders]]}, ["item_code", "bom_no", "warehouse", "rate", "uom", "qty"])
        print("**** so_items", so_items)
        all_bom_items, consolidate_items = [],[]
        for item in source.po_items:
            bom_items = get_bom_items(item.bom_no, source.company, qty=1, fetch_exploded=1)
            print("^^^^ bom_items", bom_items)
            for b_item in bom_items:
                b_item.update({'warehouse':item.warehouse})
            all_bom_items.extend(bom_items)
        # print("8888 all_bom_items",all_bom_items)
        
        c = collections.Counter()
        for d in all_bom_items:
            c[d["item_code"]] += float(d["qty"])
        # print("CCCCCCCCCc",c)
        consolidate_items = [{"item_code":k,"qty":float(v)} for k,v in c.items()]
        # print("aaaaaaaaconsolidate_items",consolidate_items)
        for c_item in consolidate_items:
            for b_item in all_bom_items:
                if c_item.get('item_code') == b_item.get('item_code'):
                    c_item.update({'source_warehouse':b_item.get('warehouse'), 
                        'rate':b_item.get('rate'),'uom':b_item.get('stock_uom')})

             
            print("*** c_item", c_item)
            row = target.append('items', {})
            row.item_code = c_item.get('item_code')
            row.qty = get_qty_from_stock_entry(c_item.get('item_code'))
            row.consolidated_qty = c_item.get('qty')
            row.s_warehouse = c_item.get('source_warehouse')
            row.basic_rate = c_item.get('rate')
            row.valuation_rate = frappe.db.get_value("Item", c_item.get('item_code'), "valuation_rate")
            row.uom = c_item.get('uom')
            row.stock_uom = c_item.get('uom')
        for s_item in so_items:
            row = target.append('items', {})
            row.item_code = s_item.get('item_code')
            row.qty = s_item.get('qty')
            row.t_warehouse = s_item.get('warehouse') 
            row.basic_rate = s_item.get('rate') 
            row.valuation_rate = frappe.db.get_value("Item", s_item.get('item_code'), "valuation_rate") 
            row.uom = s_item.get('uom')
            row.stock_uom = s_item.get('uom')

      
    
    doclist = get_mapped_doc("Production Plan", source_name,    {
        "Production Plan": {
            "doctype": "Stock Entry",
            # "field_map": {
            #     "stock_entry_type": "Manufacture"
            # },
            # "validation": {
            #     "docstatus": ["=", 1]
            # }
        },
        # "Stock Entry Detail": {
        #   "doctype": "Stock Entry Detail",
            # "field_map": {
            #   "name": "ste_detail",
            #   "parent": "against_stock_entry",
            #   "serial_no": "serial_no",
            #   "batch_no": "batch_no"
            # },
            # "postprocess": update_item,
            # "condition": lambda doc: flt(doc.qty) - flt(doc.transferred_qty) > 0.01
        # },
    }, target_doc, set_missing_values)

    return doclist

def get_qty_from_stock_entry(item_code):
    se_qty = frappe.db.sql("""SELECT sd.qty from `tabStock Entry` as s 
        inner join `tabStock Entry Detail` as sd where sd.item_code = '{0}'
        and s.stock_entry_type = 'Material Transfer' and s.docstatus=1""".format(item_code), as_dict=1, debug=1)
    print("######## se_qty",se_qty)
    ste_qty = 0.0
    for s in se_qty:
        # print("!!!!!!!!!!!s", s)
        ste_qty += s.qty 
    return ste_qty

def get_qty_from_bom(all_bom_items,item_code):        
    c = collections.Counter()
    for d in all_bom_items:
        c[d["item_code"]] += float(d["qty"])
    # print("CCCCCCCCCc",c)
    consolidate_items = [{"item_code":k,"qty":float(v)} for k,v in c.items()]
    print("^^^^^consolidate_items", consolidate_items)
    for b_item in consolidate_items:
        if item_code == b_item.get('item_code'):
            return b_item.get('qty')

def get_qty_from_single_bom(all_bom_items, item_code):
    for b_item in all_bom_items:
        if item_code == b_item.get('item_code'):
            return b_item.get('qty')

def percentage(percent, whole):
  return (percent * whole) / 100.0

def get_exploded_bom_items(bom_no, company,warehouse=None):
    bom_items = get_bom_items(bom_no, company, qty=1, fetch_exploded=1)
    print("^^^^ bom_items", bom_items)
    for b_item in bom_items:
        b_item.update({'warehouse':warehouse})
    return bom_items

def get_final_qty(all_bom_items, item_code):
    # print("8888 all_bom_items",all_bom_items)
    # from collections import defaultdict
    from collections import Counter
    
    item_count_list = list(collections.Counter(i['item_code'] for i in all_bom_items).items())
    print("***** item_count_list",item_count_list, type(item_count_list))
    for item in item_count_list:
        print("..................... item",item_code ,item[0])
        # final_qty = 0.0
        if item_code == item[0]:
            print("@@@ item", item, item[0])
            stk_qty = get_qty_from_stock_entry(item[0])
            print("@@@@ stk_qty",stk_qty)
            final_qty = stk_qty if stk_qty else 0
            if item[1] > 1:
                bom_qty = get_qty_from_bom(all_bom_items,item[0])
                print("**** bom_qty",bom_qty)
                if bom_qty and stk_qty:
                    diff = bom_qty - stk_qty
                    print("&& diff", diff)
                    single_bom_qty = get_qty_from_single_bom(all_bom_items,item[0])
                    print("**** single_bom_qty",single_bom_qty)
                    percent_bom_qty = percentage(single_bom_qty, bom_qty)
                    print("#### percent_bom_qty",percent_bom_qty)
                    final_percent = percentage(percent_bom_qty, diff)
                    final_qty = final_percent if final_percent else 0
            return final_qty

@frappe.whitelist()
def make_stock_entry(doc):
    # print("//////doc", doc, type(doc))
    doc = json.loads(doc)
    # print("///docdoc.get('sales_orders')",doc.get("sales_orders"))
    so_items = frappe.db.get_list("Sales Order Item", {'parent': ["in", [s.get('sales_order') for s in doc.get("sales_orders")]]}, ["item_code", "bom_no", "warehouse", "rate", "uom", "qty", 'parent'])
    print("**** so_items", so_items)
    all_bom_items = []
    for item in doc.get('po_items'):
        for s_item in so_items:
            # print(">>>>>>>>>>>>>>> s_item",s_item, s_item.keys(), s_item.get('qty'))
            if item.get('item_code') == s_item.get('item_code'):
                s_item['bom_no'] = item.get('bom_no')
        bom_items = get_exploded_bom_items(item.get('bom_no'), doc.get('company'),item.get('warehouse'))
        all_bom_items.extend(bom_items)
    
    for item in so_items:
        bom_items = get_exploded_bom_items(item.get('bom_no'), doc.get('company'),item.get('warehouse'))
        stk_doc = frappe.new_doc("Stock Entry")
        stk_doc.stock_entry_type = "Manufacture"
        stk_doc.production_plan = doc.get('name')
        stk_doc.sales_order = item.get('parent')
        print("^^^^^^^ item",item)
        for b_item in bom_items:
            print("/////b_item", b_item)
            b_item['s_warehouse'] = b_item.get('default_warehouse')
            b_item['basic_rate'] = b_item.get('rate') 
            b_item['valuation_rate'] = frappe.db.get_value("Item", b_item.get('item_code'), "valuation_rate") 
            b_item['uom'] = b_item['stock_uom'] = b_item.get('uom')
            # b_item.stock_uom = b_item.get('uom')
            final_qty = get_final_qty(all_bom_items, b_item.get('item_code'))
            print("@@@ final_qty",final_qty,b_item.get('item_code') )
            if final_qty > 0:
                print("^^^^^^ if final_qty")
                b_item['qty'] = final_qty 
            else:
                print("^^^^^^ else final_qty")
                bom_items.remove(b_item)
            stk_doc.append("items", b_item)
        item['t_warehouse'] = item.get('warehouse')
        item['basic_rate'] = item.get('rate') 
        item['valuation_rate'] = frappe.db.get_value("Item", item.get('item_code'), "valuation_rate") 
        item['uom'] = item['stock_uom'] = item.get('stock_uom')
        item['is_finished_item'] = 1
        stk_doc.append("items", item)
        print("*** stk_doc", stk_doc.__dict__)
        stk_doc.save()
        frappe.msgprint(_("Stock Entry created.".format(stk_doc.name)))
       
    

  