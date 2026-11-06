import json,math,struct,tempfile,unittest
from pathlib import Path
from imu_mount import G,ImuMount

def rows(m,accel,tenths,speed=0.0,gyro=(0.0,0.0,0.0)):
    """tenths x 0.1 s of 100 Hz rows; returns the last car-axis output."""
    out=None
    for _ in range(tenths*10):out=m.add(list(accel),list(gyro),speed)
    return out

def near(case,expected,actual,tol):
    for e,a in zip(expected,actual):case.assertAlmostEqual(e,a,delta=tol)

UP=[0.0,0.0,G]  # flat, BNO055 Z up

class ImuMountTests(unittest.TestCase):
    def test_auto_level_needs_two_still_seconds(self):
        m=ImuMount()
        self.assertIsNone(rows(m,UP,19));self.assertIsNone(m.up)
        rows(m,UP,1);near(self,[0,0,1],m.up,1e-9)
    def test_no_auto_level_without_speed_or_while_moving_or_turning(self):
        m=ImuMount()
        rows(m,UP,40,speed=None);rows(m,UP,40,speed=15.0);rows(m,UP,40,gyro=(0,0,5.0))
        self.assertIsNone(m.up)
    def test_manual_level_works_indoors_and_is_kept(self):
        m=ImuMount()
        rows(m,[G,0,0],20,speed=None)
        self.assertTrue(m.level_now());self.assertTrue(m.manual)
        rows(m,UP,20)  # a later stop at another angle does not overwrite it, but is reported
        near(self,[1,0,0],m.up,1e-9);self.assertTrue(m.moved)
        self.assertIn('10°以上違います',m.public()['message'])
    def test_manual_level_refuses_a_shaking_logger(self):
        m=ImuMount()
        for k in range(200):m.add([0,0,G+(1.0 if k//10%2 else -1.0)],[0,0,0],None)
        self.assertFalse(m.level_now())
    def test_intended_mounting_gives_car_axes_before_forward_is_learned(self):
        m=ImuMount();rows(m,UP,20)
        # +X forward, so the car's right is BNO055 -Y; gravity is removed from the vertical.
        near(self,[0.2,0.5,0.1],m.vehicle([0.2*G,-0.5*G,1.1*G]),1e-9)
        self.assertIn('X軸を前と仮定中',m.public()['message'])
    def test_vertical_removes_the_measured_gravity(self):
        m=ImuMount();rows(m,[0,0,G*0.99],20)  # accelerometer reading 1 % low
        self.assertAlmostEqual(rows(m,[0,0,G*0.99],1)[2],0,delta=1e-9)
    def test_tilted_mounting(self):
        a=math.radians(40);up=[0,math.sin(a),math.cos(a)]  # leaning 40° about X
        m=ImuMount();rows(m,[G*u for u in up],20)
        self.assertAlmostEqual(m.public()['tilt_deg'],40,delta=.1)
        near(self,[0.3,0,0],m.vehicle([G*u+(0.3*G if i==0 else 0) for i,u in enumerate(up)]),1e-9)
    def drive(self,m,fwd,up=(0,0,1),fixes_per_s=10,heading=lambda k:90.0,steps=30):
        """Speed up and slow down along fwd on a straight road, GNSS at fixes_per_s."""
        itow=100000;v=5.0;m.on_fix(itow,v,heading(0))
        for k in range(steps):
            acc=0.6 if k%2==0 else -0.5
            for _ in range(fixes_per_s):
                rows(m,[G*up[i]+fwd[i]*acc for i in range(3)],10//fixes_per_s,speed=v*3.6)
                itow+=1000//fixes_per_s;v+=acc/fixes_per_s;m.on_fix(itow,v,heading(k))
    def test_forward_is_learned_from_gnss_at_10hz(self):
        m=ImuMount();rows(m,UP,20)
        self.drive(m,[0,-1,0])  # mounted turned 90° as in the eco car (X left, Y back)
        self.assertTrue(m.forward_learned);near(self,[0,-1,0],m.forward(),1e-6)
        self.assertEqual(m.public()['forward_from_x_deg'],-90);self.assertIn('X軸から右へ90°',m.public()['message'])
        near(self,[2/G,0,0],m.vehicle([0,-2.0,G]),1e-6)
    def test_turning_is_not_used_for_forward(self):
        m=ImuMount();rows(m,UP,20)
        self.drive(m,[0,-1,0],heading=lambda k:20.0*k)
        self.assertFalse(m.forward_learned)
    def test_remounting_at_a_stop_starts_over(self):
        m=ImuMount();rows(m,UP,20);self.drive(m,[0,-1,0]);self.assertTrue(m.forward_learned)
        rows(m,[G,0,0],20);near(self,[1,0,0],m.up,1e-9);self.assertFalse(m.forward_learned)
    def test_stops_blend_in_small_changes(self):
        m=ImuMount();rows(m,UP,20)
        a=math.radians(2);rows(m,[0,G*math.sin(a),G*math.cos(a)],20)
        self.assertTrue(0<m.up[1]<math.sin(a))
    def test_saved_file_round_trip_and_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'imu_mount.json';m=ImuMount(path);rows(m,UP,20);self.drive(m,[0,-1,0]);m.save()
            copy=ImuMount(path);near(self,m.up,copy.up,1e-4);near(self,m.forward(),copy.forward(),1e-4);self.assertTrue(copy.forward_learned)
            state=m.state();self.assertIs(state,m.state())  # the same object until something changes
            path.write_text('{"up":[0,0,0]}');broken=ImuMount(path);self.assertIsNone(broken.up);self.assertTrue(broken.error)
            m.clear();self.assertIsNone(ImuMount(path).up)
    def test_pvt_feeds_new_fixes_only(self):
        m=ImuMount();nav=bytearray(92);nav[20]=3;nav[21]=1;struct.pack_into('<I',nav,0,5000);struct.pack_into('<i',nav,60,8000)
        m.on_pvt(bytes(nav));self.assertEqual(m.last_fix[:2],(5000,8.0))
        m.on_pvt(None);self.assertIsNone(m.last_fix)

class LowPassTests(unittest.TestCase):
    """The G outputs are low-passed so the screens' G ball does not shake with the car."""
    def leveled(self):
        m=ImuMount();rows(m,UP,20);return m
    def test_vibration_is_removed_and_a_steady_g_is_kept(self):
        m=self.leveled();out=[]
        for k in range(300):  # 0.3 G lateral + 0.5 G of 40 Hz shaking (NCEC on the road)
            out.append(m.add([0,-0.3*G+0.5*G*math.sin(2*math.pi*40*k/100),G],[0,0,0],50.0)[1])
        tail=out[200:]
        self.assertAlmostEqual(sum(tail)/len(tail),0.3,delta=0.005)
        self.assertLess(max(tail)-min(tail),0.02)  # 1.0 G peak to peak in, under 0.02 G out
    def test_a_step_takes_about_a_tenth_of_a_second(self):
        m=self.leveled();out=[m.add([0.5*G,0,G],[0,0,0],50.0)[0] for _ in range(100)]
        half=next(i for i,v in enumerate(out) if v>=0.25)
        self.assertTrue(8<=half<=15,half)  # 2 Hz Butterworth: half way after about 0.11 s
        self.assertLess(max(out),0.5*1.06);self.assertAlmostEqual(out[-1],0.5,delta=0.005)
    def test_starts_from_the_first_row_and_after_a_gap(self):
        m=ImuMount();rows(m,UP,20)
        m.restart();self.assertAlmostEqual(m.add([0.4*G,0,G],[0,0,0],50.0,ms=1000)[0],0.4,delta=1e-9)
        m.add([0.4*G,0,G],[0,0,0],50.0,ms=1010)
        self.assertAlmostEqual(m.add([-0.2*G,0,G],[0,0,0],50.0,ms=1500)[0],-0.2,delta=1e-9)  # 490 ms gap
        self.assertGreater(m.add([0.4*G,0,G],[0,0,0],50.0,ms=1510)[0],-0.2)  # 10 ms: filtered again
    def test_the_vertical_has_no_start_up_transient(self):
        m=ImuMount();out=[m.add([0,0,G],[0,0,0],0.0) for _ in range(400)]
        self.assertTrue(all(abs(o[2])<1e-9 for o in out if o))

class DecoderTests(unittest.TestCase):
    def test_hardware_decoder_writes_car_axes_and_the_calibration(self):
        from hardware import HardwareDecoder
        from models import Configuration
        decoder=HardwareDecoder();nav=bytearray(92);nav[20]=3;nav[21]=1
        raw=bytearray(46);struct.pack_into('<3h',raw,0,0,0,981);struct.pack_into('<3h',raw,32,50,0,0)  # BNO055 linear accel says 0.05 G
        state={'mcu_ms':0,'gnss_at':0,'nav':nav.hex(),'imu_address':40,'sd_ready':1,'can_counts':[0,0]}
        for k in range(21):
            stamp=k*100;state.update(mcu_ms=stamp+10,gnss_at=stamp);struct.pack_into('<I',nav,0,stamp);state['nav']=nav.hex()
            samples,_=decoder.decode(state,{'rows':[[k*10+i,stamp+i*10,raw.hex()] for i in range(10)],'can':[]},Configuration())
        s=samples[-1]
        self.assertAlmostEqual(s['values']['LongAccel'],0,delta=1e-9)  # the car is still: not BNO055's 0.05 G
        self.assertEqual(s['imu_mount']['up'],[0,0,1.0]);json.dumps(s['imu_mount'])

if __name__=='__main__':unittest.main()
