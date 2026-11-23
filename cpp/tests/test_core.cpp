#include "EmbeddedJournal.h"
#include <cassert>
using namespace lord_sumi;
int main(){
 EmbeddedJournal j;int32_t v=0;
 assert(j.get(1,v)==JournalStatus::Missing);
 assert(j.put(1,-12,0)==JournalStatus::Ok);
 assert(j.get(1,v)==JournalStatus::Ok && v==-12);
 assert(j.put(1,5,1)==JournalStatus::Ok);
 assert(j.revision()==2);
 assert(j.put(2,3,1)==JournalStatus::Invalid);
 assert(j.fault());assert(j.get(1,v)==JournalStatus::Fault);
 j.reset();
 for(unsigned i=1;i<=16;++i)assert(j.put((uint16_t)i,(int32_t)i,j.revision())==JournalStatus::Ok);
 assert(j.put(17,17,j.revision())==JournalStatus::Full);
}
