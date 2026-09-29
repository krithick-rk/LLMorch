// reset_ctrl.sv — Synchronous/Asynchronous Reset Controller IP
module reset_ctrl (
    input  logic clk_i,
    input  logic rst_ni,
    input  logic sw_rst_req_i,
    output logic rst_core_no,
    output logic rst_periph_no
);

  logic [1:0] sync_stages;

  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      sync_stages <= 2'b00;
    end else begin
      sync_stages <= {sync_stages[0], ~sw_rst_req_i};
    end
  end

  assign rst_core_no   = sync_stages[1];
  assign rst_periph_no = sync_stages[1];

endmodule
