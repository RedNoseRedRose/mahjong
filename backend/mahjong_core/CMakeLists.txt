cmake_minimum_required(VERSION 3.5)
project(mahjong_core)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 REQUIRED)

pybind11_add_module(mahjong_core mahjong_core.cpp)