execute_process(COMMAND "${BENCHMARK}" --backend gpu --samples 10000
                RESULT_VARIABLE status OUTPUT_VARIABLE output ERROR_VARIABLE error)
if(NOT status EQUAL 1 OR NOT error MATCHES "GPU unavailable")
  message(FATAL_ERROR "Expected a clear GPU-unavailable failure; exit=${status}, stderr=${error}")
endif()
