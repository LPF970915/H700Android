// SPDX-License-Identifier: Apache-2.0
#include "Model.h"
#include <cassert>
#include <sys/stat.h>
#include <iostream>
void put(const std::string&p,const std::string&v){std::ofstream f(p);f<<v;assert(f.good());}
int main(int argc,char**argv){assert(argc==2);std::string root=argv[1];assert(mkdir(root.c_str(),0700)==0);
 auto cpu=root+"/thermal_zone7";assert(!mkdir(cpu.c_str(),0700));put(cpu+"/type","cpu_thermal_zone\n");put(cpu+"/temp","45000\n");
 put(cpu+"/trip_point_0_type","passive");put(cpu+"/trip_point_0_temp","60000");put(cpu+"/trip_point_1_type","passive");put(cpu+"/trip_point_1_temp","70000");put(cpu+"/trip_point_2_type","critical");put(cpu+"/trip_point_2_temp","115000");
 auto battery=root+"/thermal_zone9";assert(!mkdir(battery.c_str(),0700));put(battery+"/type","axp2202-battery");put(battery+"/temp","30000");
 auto sensors=roc::sensors(root);assert(sensors.size()==2&&sensors[0].value==45&&sensors[0].type==0&&sensors[1].type==2);assert(std::isnan(sensors[1].hot[6]));
 for(const auto&p:std::vector<std::pair<float,int>>{{59.999f,0},{60,1},{69.999f,1},{70,2},{114.999f,2},{115,6}})assert(roc::severity(p.first,sensors[0].hot)==p.second);
 put(cpu+"/temp","nan");assert(std::isnan(roc::sensors(root)[0].value));put(cpu+"/temp","999999999");assert(std::isnan(roc::sensors(root)[0].value));put(cpu+"/temp","45000 trailing");assert(std::isnan(roc::sensors(root)[0].value));
 auto c=root+"/cooling_device12";assert(!mkdir(c.c_str(),0700));put(c+"/type","thermal-cpufreq-0");put(c+"/cur_state","3");put(c+"/max_state","8");auto cs=roc::coolers(root);assert(cs.size()==1&&cs[0].type==2&&cs[0].value==3);put(c+"/cur_state","-1");assert(roc::coolers(root).empty());put(c+"/cur_state","9");assert(roc::coolers(root).empty());put(c+"/cur_state","0");put(c+"/type","thermal-devfreq-0");assert(roc::coolers(root)[0].type==6);
 assert(roc::sensors(root+"/absent").empty());std::cout<<"THERMAL_MODEL_REAL_UNITS_THRESHOLDS_NAN_COOLING_PASS\n";}
