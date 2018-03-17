# Copyright (c) 2018, MD2K Center of Excellence
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
from cerebralcortex.cerebralcortex import CerebralCortex
from core.computefeature import ComputeFeatureBase
from core.feature.respirationstatistics.utils.peak_valley import \
    compute_peak_valley
from core.feature.respirationstatistics.utils.\
    rip_cycle_feature_computation import rip_cycle_feature_computation

from core.feature.respirationstatistics.utils.get_store import get_stream_days
from core.feature.respirationstatistics.utils.util import *

CC = CerebralCortex()
users = CC.get_all_users("mperf-alabsi")
respiration_raw_autosenseble = "RESPIRATION--org.md2k.autosenseble--AUTOSENSE_BLE--CHEST"
respiration_baseline_autosenseble = "RESPIRATION_BASELINE--org.md2k.autosenseble--AUTOSENSE_BLE--CHEST"
for user in users:
    streams = CC.get_user_streams(user['identifier'])
    user_id = user["identifier"]
    if respiration_raw_autosenseble in streams:
        stream_days = get_stream_days(streams[respiration_raw_autosenseble]["identifier"],CC)

        if not stream_days:
            continue

        for day in stream_days:
            rip_raw = CC.get_stream(streams[respiration_raw_autosenseble]["identifier"], day=day,
                                    user_id=user_id)
            rip_baseline = CC.get_stream(streams[respiration_baseline_autosenseble]["identifier"],
                                         day=day, user_id=user_id)
            if not rip_raw.data:
                continue
            elif not rip_baseline.data:
                final_respiration = rip_raw.data
            else:
                final_respiration = get_recovery(rip_raw.data[1:10000],
                                                 rip_baseline.data[1:10000],25)

            respiration_final = [i for i in final_respiration if i.sample>0]
            sample = np.array([i.sample for i in respiration_final])
            ts = np.array([i.start_time.timestamp() for i in respiration_final])

            sample_smoothed_detrened = smooth_detrend(sample,ts)

            sample_filtered,ts_filtered,indexes =filter_bad_rip(ts,sample_smoothed_detrened)
            respiration_final_smoothed_detrended_filtered =np.array(respiration_final)[indexes]

            peak,valley = compute_peak_valley(rip=respiration_final_smoothed_detrended_filtered)

            feature = rip_cycle_feature_computation(peak,valley)
            inspiration_duration, expiration_duration, respiration_duration, \
            inspiration_expiration_ratio, stretch= feature[2:7]

            cycle_quality, corr_pre_cycle,corr_post_cycle = \
                return_neighbour_cycle_correlation(sample_filtered,
                                                   valley,
                                                   inspiration_duration)
            quality_area_velocity_shape = \
                respiration_area_shape_velocity_calculation(sample_filtered,
                                                            ts_filtered,peak,
                                                            valley,cycle_quality)
            cycle_quality,area_Inspiration,area_Expiration, \
            area_Respiration,area_ie_ratio, \
            velocity_Inspiration,velocity_Expiration, shape_skew, shape_kurt \
                = quality_area_velocity_shape

            entropy_array = spectral_entropy_calculation(sample_filtered,
                                                         ts_filtered,
                                                         peak,valley,
                                                         cycle_quality)

            energyX,FQ_05_2_Hz,FQ_201_4_Hz,FQ_401_6_Hz,FQ_601_8_Hz,\
            FQ_801_1_Hz = spectral_energy_calculation(sample_filtered,ts_filtered,peak,valley,
                             cycle_quality)

            conversation_feature = []
            for i,dp in enumerate(cycle_quality):
                if dp.sample == Quality.UNACCEPTABLE:
                    continue
                temp = np.zeros((21,))
                temp[0] = inspiration_duration[i].sample;temp[1] = expiration_duration[i].sample
                temp[2] = respiration_duration[i].sample;temp[3] = temp[0]/temp[1];
                temp[4] = stretch[i].sample;
                temp[5] = velocity_Inspiration[i].sample;
                temp[6] = velocity_Expiration[i].sample
                temp[7] = shape_skew[i].sample
                temp[8] = shape_kurt[i].sample;
                temp[9] = entropy_array[i].sample;temp[10] = temp[5]/temp[6];
                temp[11] = area_ie_ratio[i].sample;temp[12] = temp[1]/temp[2];
                temp[13] = area_Respiration[i].sample/temp[0];
                temp[14] = FQ_05_2_Hz[i].sample;temp[15] = FQ_201_4_Hz[i].sample;
                temp[16] = FQ_401_6_Hz[i].sample;temp[17] = FQ_601_8_Hz[i].sample;
                temp[18] = FQ_801_1_Hz[i].sample;temp[19] = corr_pre_cycle[i].sample;
                temp[20] = corr_post_cycle[i].sample
                conversation_feature.append(deepcopy(dp))
                conversation_feature[-1].sample = temp
