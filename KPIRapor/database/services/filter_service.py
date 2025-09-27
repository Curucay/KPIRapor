import streamlit as st
import pandas as pd
from database.services.base.base_service import BaseService

class FilterService(BaseService):
    @staticmethod
    @st.cache_data(show_spinner=False, ttl=300)
    def get_branches():
        """Şube listesini getir"""
        sql = f'''
            SELECT 
                "Id",
                "Name" ,
                "ERPConnectionCode"
            FROM "Branchs" 
            ORDER BY "Name"
            '''
        return FilterService.execute_query(sql)

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=300)
    def get_departments(branch_ids):
        """Departman listesini getir"""
        if not branch_ids:
            return pd.DataFrame(columns=["Id", "Name"])

        # Cache için tuple'a çevir
        branch_ids = tuple(branch_ids)

        placeholders = ",".join(["%s"] * len(branch_ids))

        sql = f'''
                SELECT 
                       "Id",
                       "Name" 
                FROM "Departments" 
                WHERE "BranchId" IN ({placeholders})
                ORDER BY "Name"
            '''

        params = list(branch_ids)

        return FilterService.execute_query(sql, params)

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=300)
    def get_groups(department_ids):
        """Bölüm listesini getir"""
        if not department_ids:
            return pd.DataFrame(columns=["Id", "Definition"])

        # Cache için tuple'a çevir
        department_ids = tuple(department_ids)

        placeholders = ",".join(["%s"] * len(department_ids))

        sql = f'''
                SELECT 
                       "Id",
                       "Name" 
                FROM "Groups" 
                WHERE "DepartmentId" IN ({placeholders})
                ORDER BY "Name"
            '''

        params = list(department_ids)

        return FilterService.execute_query(sql, params)

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=300)
    def get_machines_by_branches_and_departments(branch_ids,departmant_ids, group_ids):
        """Şube, departman ve bölüme göre makine listesi"""
        if not branch_ids or not departmant_ids or not group_ids:
            return pd.DataFrame(columns=["Id", "Definition", "Code", "BranchId"])

        # Cache için tuple'a çevir
        branch_ids = tuple(branch_ids)
        departmant_ids = tuple(departmant_ids)
        group_ids = tuple(group_ids)

        branch_placeholders = ",".join(["%s"] * len(branch_ids))
        departmant_placeholders = ",".join(["%s"] * len(departmant_ids))
        group_placeholders = ",".join(["%s"] * len(group_ids))

        sql = f'''
                SELECT "Id","Definition","Code","BranchId"
                FROM "Machines"
                WHERE "BranchId" IN ({branch_placeholders})
                AND "DepartmentId" IN ({departmant_placeholders})
                AND "GroupId" IN ({group_placeholders})
                ORDER BY "Definition"
            '''
        params = list(branch_ids + departmant_ids + group_ids)

        return FilterService.execute_query(sql, params)
