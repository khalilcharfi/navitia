#include "to_proto.h"
#include "type/to_proto.h"
#include "boost/foreach.hpp"
namespace itineraires {

void to_proto(etape et, pbnavitia::Parcours_Etape *etpb, navitia::type::Data &data) {
    etpb->set_ligne(et.ligne);
    etpb->set_descente(data.pt_data.stop_areas.at(et.descente).name);
}

void to_proto(parcours pa, pbnavitia::Parcours *papb, navitia::type::Data &data) {

    BOOST_FOREACH(itineraires::etape e, pa.etapes) {
        to_proto(e, papb->add_etapes(), data);
    }
}

void to_proto(itineraire it,std::map<uint32_t, itineraires::parcours> &map_parcours, navitia::type::Data &data, pbnavitia::Itineraire *itpb) {

    to_proto(map_parcours[it.parcours], itpb->mutable_parcours(), data);


    unsigned int count = 0;
    pbnavitia::StopTimeEtape *ste;
    BOOST_FOREACH(uint32_t st, it.stop_times) {
        if((count%2) == 0) {
            ste = itpb->add_stop_times();
            navitia::type::to_proto(data.pt_data.stop_times.at(st), ste->mutable_depart());
        } else {
            navitia::type::to_proto(data.pt_data.stop_times.at(st), ste->mutable_arrivee());
        }
        count ++;

    }
}
}
