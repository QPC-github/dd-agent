import unittest
import time
import threading
from aggregator import MetricsAggregator
from dogstatsd import Dogstatsd, init, Server
from util import PidFile
from config import start_jmx_connector
import os
import signal   

STATSD_PORT = 8129
class DummyReporter(threading.Thread):
    def __init__(self, metrics_aggregator):
        threading.Thread.__init__(self)
        self.finished = threading.Event()
        self.metrics_aggregator = metrics_aggregator
        self.interval = 4
        self.metrics = None
        self.finished = False
        self.start()


    def run(self):
        while not self.finished:
            time.sleep(self.interval)
            self.flush()

    def flush(self):
        metrics = self.metrics_aggregator.flush()
        if metrics:
            self.metrics = metrics

class JMXTestCase(unittest.TestCase):
    def setUp(self):
        aggregator = MetricsAggregator("test_host")
        self.server = Server(aggregator, "localhost", STATSD_PORT)
        pid_file = PidFile('dogstatsd')
        self.reporter = DummyReporter(aggregator)
        
        self.t1 = threading.Thread(target=self.server.start)
        self.t1.start()

        confd_path = os.path.realpath(os.path.join(os.path.abspath(__file__), "..", "jmx_yamls"))
        self.jmxfetch_pid = start_jmx_connector(confd_path, {}, statsd_port=STATSD_PORT)



    def tearDown(self):
        self.server.stop()
        self.reporter.finished = True
        os.kill(self.jmxfetch_pid, signal.SIGKILL)


    def testCustomJMXMetric(self):
        count = 0
        while self.reporter.metrics is None:
            time.sleep(1)
            count += 1
            if count > 20:
                raise Exception("No metrics were received in 20 seconds")

        metrics = self.reporter.metrics

        self.assertTrue(type(metrics) == type([]))
        self.assertTrue(len(metrics) > 0)
        self.assertEquals(len([t for t in metrics if t['metric'] == "my.metric.buf" and "instance:jmx_instance1" in t['tags']]), 1, metrics)
        self.assertTrue(len([t for t in metrics if 'type:ThreadPool' in t['tags'] and "instance:jmx_instance1" in t['tags'] and "jmx.catalina" in t['metric']]) > 8, metrics)
        self.assertTrue(len([t for t in metrics if "jmx.java.lang" in t['metric'] and "instance:jmx_instance1" in t['tags']]) > 40, metrics)
        self.assertTrue(len([t for t in metrics if "jvm." in t['metric'] and "instance:jmx_instance1" in t['tags']]) == 6, metrics)

        

if __name__ == "__main__":
    unittest.main()
