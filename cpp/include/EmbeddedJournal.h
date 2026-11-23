#pragma once
#include <stdint.h>
#include <stddef.h>
namespace lord_sumi {
enum class JournalStatus { Ok, Missing, Invalid, Full, Fault };
class EmbeddedJournal {
 struct Entry {uint16_t key; int32_t value;};
 Entry items_[16]; size_t count_; uint32_t revision_; bool fault_;
public:
 EmbeddedJournal():count_(0),revision_(0),fault_(false){}
 uint32_t revision() const{return revision_;}
 bool fault() const{return fault_;}
 void reset(){count_=0;revision_=0;fault_=false;}
 JournalStatus put(uint16_t key,int32_t value,uint32_t expected){
  if(fault_)return JournalStatus::Fault;
  if(key==0 || expected!=revision_ || revision_==UINT32_MAX){fault_=true;return JournalStatus::Invalid;}
  for(size_t i=0;i<count_;++i)if(items_[i].key==key){items_[i].value=value;++revision_;return JournalStatus::Ok;}
  if(count_==16){fault_=true;return JournalStatus::Full;}
  items_[count_++]={key,value};++revision_;return JournalStatus::Ok;
 }
 JournalStatus get(uint16_t key,int32_t& value)const{
  if(fault_)return JournalStatus::Fault;
  if(key==0)return JournalStatus::Invalid;
  for(size_t i=0;i<count_;++i)if(items_[i].key==key){value=items_[i].value;return JournalStatus::Ok;}
  return JournalStatus::Missing;
 }
};
}
