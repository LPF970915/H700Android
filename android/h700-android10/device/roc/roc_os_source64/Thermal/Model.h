// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <array>
#include <cmath>
#include <fstream>
#include <glob.h>
#include <limits>
#include <string>
#include <vector>
namespace roc {
inline float unknown() { return std::numeric_limits<float>::quiet_NaN(); }
inline std::string text(const std::string& p) { std::ifstream f(p); std::string s; std::getline(f,s); return s; }
inline bool number(const std::string& p, long long& v) { std::ifstream f(p); std::string tail; return bool(f>>v) && !(f>>tail); }
inline std::vector<std::string> paths(const std::string& p) { glob_t g{}; std::vector<std::string> r; if(!glob(p.c_str(),0,nullptr,&g)) for(size_t i=0;i<g.gl_pathc;i++) r.emplace_back(g.gl_pathv[i]); globfree(&g); return r; }
struct Sensor { std::string name; int type=-1; float value=unknown(); std::array<float,7> hot; int severity=0; Sensor(){hot.fill(unknown());} };
inline int severity(float value,const std::array<float,7>& h) { int r=0; for(int i=1;i<7;i++) if(std::isfinite(value)&&std::isfinite(h[i])&&value>=h[i]) r=i; return r; }
inline std::vector<Sensor> sensors(const std::string& root="/sys/class/thermal") {
 std::vector<Sensor> r;
 for(const auto& p:paths(root+"/thermal_zone*")) {
  Sensor s; s.name=text(p+"/type");
  if(s.name=="cpu_thermal_zone") s.type=0;
  else if(s.name=="gpu_thermal_zone") s.type=1;
  else if(s.name=="axp2202-battery") s.type=2;
  else if(s.name!="ve_thermal_zone" && s.name!="ddr_thermal_zone") continue;
  long long n; if(number(p+"/temp",n)&&n>=-40000&&n<=150000) s.value=n/1000.f;
  // Use exposed kernel trip points, not guessed battery/skin limits.
  int passive=0;
  for(const auto& trip:paths(p+"/trip_point_*_type")) {
   const auto kind=text(trip); auto temp=trip.substr(0,trip.size()-4)+"temp";
   if(!number(temp,n)||n<0||n>150000) continue;
   if(kind=="passive" && passive<2) s.hot[++passive]=n/1000.f;
   else if(kind=="critical") s.hot[6]=n/1000.f;
  }
  s.severity=severity(s.value,s.hot); r.push_back(s);
 }
 return r;
}
struct Cooler {std::string name; int type; unsigned long long value;};
inline std::vector<Cooler> coolers(const std::string& root="/sys/class/thermal") {
 std::vector<Cooler> r;
 for(const auto& p:paths(root+"/cooling_device*")) {auto name=text(p+"/type"); long long n,max;
  if(!number(p+"/cur_state",n)||!number(p+"/max_state",max)||n<0||n>max) continue;
  // devfreq can represent several components; do not guess GPU identity.
  int type=name.find("thermal-cpufreq")==0?2:6;
  r.push_back({name,type,static_cast<unsigned long long>(n)});
 } return r;
}
}
